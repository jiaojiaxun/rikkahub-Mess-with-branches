package me.rerere.rikkahub.data.ble

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import androidx.core.content.ContextCompat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.util.UUID

/**
 * Receives the standard BLE Heart Rate Profile (service 0x180D, measurement 0x2A37).
 * Works with watches that expose a "heart rate broadcast" (e.g. Xiaomi Watch S4) —
 * the profile is intentionally unencrypted, so no vendor pairing key is needed.
 *
 * Lifecycle: process-wide singleton; the GATT connection stays open until [disconnect]
 * so the reading survives dialog close and page switches.
 */
object HeartRateMonitor {

    private val HR_SERVICE_UUID: UUID = UUID.fromString("0000180d-0000-1000-8000-00805f9b34fb")
    private val HR_MEASUREMENT_UUID: UUID = UUID.fromString("00002a37-0000-1000-8000-00805f9b34fb")
    private val CCC_UUID: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

    private const val PREFS = "heart_rate_monitor"
    private const val KEY_NAME = "last_device_name"
    private const val KEY_ADDR = "last_device_address"
    private const val SCAN_TIMEOUT_MS = 15_000L
    private const val CONNECT_TIMEOUT_MS = 15_000L

    data class DiscoveredDevice(
        val name: String,
        val address: String,
        val rssi: Int,
    )

    data class MonitorState(
        val scanning: Boolean = false,
        val connecting: Boolean = false,
        val connected: Boolean = false,
        val deviceName: String? = null,
        val deviceAddress: String? = null,
        val bpm: Int? = null,
        val lastUpdateMillis: Long = 0L,
        val error: String? = null,
        val discovered: List<DiscoveredDevice> = emptyList(),
    )

    private val _state = MutableStateFlow(MonitorState())
    val state: StateFlow<MonitorState> = _state

    private val handler = Handler(Looper.getMainLooper())
    private var scanCallback: ScanCallback? = null
    private var gatt: BluetoothGatt? = null
    private val discoveredMap = LinkedHashMap<String, DiscoveredDevice>()

    fun requiredPermissions(): Array<String> =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }

    fun hasPermissions(context: Context): Boolean =
        requiredPermissions().all {
            ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED
        }

    fun isBluetoothEnabled(context: Context): Boolean =
        bluetoothAdapter(context.applicationContext)?.isEnabled == true

    private fun bluetoothAdapter(context: Context): BluetoothAdapter? =
        (context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter

    fun lastDevice(context: Context): Pair<String, String>? {
        val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val name = prefs.getString(KEY_NAME, null)
        val addr = prefs.getString(KEY_ADDR, null)
        return if (!name.isNullOrBlank() && !addr.isNullOrBlank()) name to addr else null
    }

    private fun saveLastDevice(context: Context, name: String, address: String) {
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_NAME, name)
            .putString(KEY_ADDR, address)
            .apply()
    }

    @SuppressLint("MissingPermission")
    fun startScan(context: Context) {
        val appContext = context.applicationContext
        val adapter = bluetoothAdapter(appContext)
        if (adapter == null || !adapter.isEnabled) {
            _state.value = _state.value.copy(error = "bluetooth_off")
            return
        }
        val scanner = adapter.bluetoothLeScanner
        if (scanner == null) {
            _state.value = _state.value.copy(error = "no_scanner")
            return
        }
        stopScan(appContext)
        discoveredMap.clear()
        _state.value = _state.value.copy(scanning = true, error = null, discovered = emptyList())
        val callback = object : ScanCallback() {
            @SuppressLint("MissingPermission")
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                val name = result.device.name ?: result.scanRecord?.deviceName ?: return
                val address = result.device.address ?: return
                discoveredMap[address] = DiscoveredDevice(name, address, result.rssi)
                _state.value = _state.value.copy(
                    discovered = discoveredMap.values.sortedByDescending { it.rssi },
                )
            }

            override fun onScanFailed(errorCode: Int) {
                _state.value = _state.value.copy(scanning = false, error = "scan_failed_" + errorCode)
            }
        }
        scanCallback = callback
        try {
            scanner.startScan(
                null,
                ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(),
                callback,
            )
        } catch (e: SecurityException) {
            scanCallback = null
            _state.value = _state.value.copy(scanning = false, error = "permission_denied")
            return
        }
        handler.postDelayed({ stopScan(appContext) }, SCAN_TIMEOUT_MS)
    }

    @SuppressLint("MissingPermission")
    fun stopScan(context: Context) {
        val callback = scanCallback ?: return
        scanCallback = null
        try {
            bluetoothAdapter(context.applicationContext)?.bluetoothLeScanner?.stopScan(callback)
        } catch (_: Exception) {
        }
        _state.value = _state.value.copy(scanning = false)
    }

    @SuppressLint("MissingPermission")
    fun connect(context: Context, address: String, name: String?) {
        val appContext = context.applicationContext
        val adapter = bluetoothAdapter(appContext)
        if (adapter == null || !adapter.isEnabled) {
            _state.value = _state.value.copy(error = "bluetooth_off")
            return
        }
        stopScan(appContext)
        disconnectInternal()
        val device: BluetoothDevice = try {
            adapter.getRemoteDevice(address)
        } catch (e: IllegalArgumentException) {
            _state.value = _state.value.copy(error = "bad_address")
            return
        }
        val displayName = name ?: lastDevice(appContext)?.first ?: address
        _state.value = _state.value.copy(
            connecting = true,
            connected = false,
            deviceName = displayName,
            deviceAddress = address,
            error = null,
        )
        val callback = object : BluetoothGattCallback() {
            @SuppressLint("MissingPermission")
            override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
                when (newState) {
                    BluetoothProfile.STATE_CONNECTED -> {
                        saveLastDevice(appContext, displayName, address)
                        _state.value = _state.value.copy(connecting = false, connected = true)
                        g.discoverServices()
                    }

                    BluetoothProfile.STATE_DISCONNECTED -> {
                        _state.value = _state.value.copy(connecting = false, connected = false)
                        try {
                            g.close()
                        } catch (_: Exception) {
                        }
                        if (gatt === g) gatt = null
                    }
                }
            }

            @Suppress("DEPRECATION")
            @SuppressLint("MissingPermission")
            override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
                val characteristic = g.getService(HR_SERVICE_UUID)
                    ?.getCharacteristic(HR_MEASUREMENT_UUID)
                if (characteristic == null) {
                    _state.value = _state.value.copy(error = "no_hr_service")
                    g.disconnect()
                    return
                }
                g.setCharacteristicNotification(characteristic, true)
                val descriptor = characteristic.getDescriptor(CCC_UUID)
                if (descriptor != null) {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        g.writeDescriptor(descriptor, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
                    } else {
                        descriptor.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                        g.writeDescriptor(descriptor)
                    }
                }
            }

            @Deprecated("Deprecated in Java")
            @Suppress("DEPRECATION")
            override fun onCharacteristicChanged(
                g: BluetoothGatt,
                characteristic: BluetoothGattCharacteristic,
            ) {
                if (characteristic.uuid != HR_MEASUREMENT_UUID) return
                val value = characteristic.value ?: return
                val bpm = parseHeartRate(value) ?: return
                _state.value = _state.value.copy(
                    bpm = bpm,
                    lastUpdateMillis = System.currentTimeMillis(),
                )
            }
        }
        gatt = try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                device.connectGatt(appContext, false, callback, BluetoothDevice.TRANSPORT_LE)
            } else {
                device.connectGatt(appContext, false, callback)
            }
        } catch (e: SecurityException) {
            _state.value = _state.value.copy(connecting = false, error = "permission_denied")
            return
        }
        handler.postDelayed({
            if (_state.value.connecting) {
                disconnectInternal()
                _state.value = _state.value.copy(connecting = false, error = "connect_timeout")
            }
        }, CONNECT_TIMEOUT_MS)
    }

    fun disconnect() {
        disconnectInternal()
        _state.value = _state.value.copy(connected = false, connecting = false)
    }

    @SuppressLint("MissingPermission")
    private fun disconnectInternal() {
        try {
            gatt?.disconnect()
            gatt?.close()
        } catch (_: Exception) {
        }
        gatt = null
    }

    private fun parseHeartRate(value: ByteArray): Int? {
        if (value.size < 2) return null
        val flags = value[0].toInt() and 0xFF
        val is16bit = flags and 0x01 != 0
        if (!is16bit) {
            return value[1].toInt() and 0xFF
        }
        if (value.size < 3) return null
        return (value[1].toInt() and 0xFF) or ((value[2].toInt() and 0xFF) shl 8)
    }
}
