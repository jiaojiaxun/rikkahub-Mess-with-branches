package me.rerere.rikkahub.ui.components.ai

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.ble.HeartRateMonitor
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun HeartRateDialog(
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val state by HeartRateMonitor.state.collectAsStateWithLifecycle()
    var hasPermission by remember { mutableStateOf(HeartRateMonitor.hasPermissions(context)) }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { result ->
        hasPermission = result.values.all { it }
    }
    val lastDevice = remember { HeartRateMonitor.lastDevice(context) }
    val timeFormat = remember { SimpleDateFormat("HH:mm:ss", Locale.getDefault()) }

    LaunchedEffect(hasPermission) {
        if (hasPermission &&
            !state.connected && !state.connecting &&
            HeartRateMonitor.isBluetoothEnabled(context)
        ) {
            HeartRateMonitor.startScan(context)
        }
    }
    DisposableEffect(Unit) {
        onDispose {
            HeartRateMonitor.stopScan(context)
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.heart_rate_title)) },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = state.bpm?.toString() ?: "--",
                        fontSize = 48.sp,
                        fontWeight = FontWeight.Bold,
                        color = if (state.connected) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(
                        text = stringResource(R.string.heart_rate_bpm_unit),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    text = when {
                        state.connected -> stringResource(
                            R.string.heart_rate_connected_to,
                            state.deviceName ?: "",
                        )
                        state.connecting -> stringResource(R.string.heart_rate_connecting)
                        state.scanning -> stringResource(R.string.heart_rate_scanning)
                        else -> stringResource(R.string.heart_rate_not_connected)
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (state.lastUpdateMillis > 0L) {
                    Text(
                        text = stringResource(
                            R.string.heart_rate_last_update,
                            timeFormat.format(Date(state.lastUpdateMillis)),
                        ),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                state.error?.let { error ->
                    Text(
                        text = error,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }

                if (!hasPermission) {
                    Text(
                        text = stringResource(R.string.heart_rate_permission_hint),
                        style = MaterialTheme.typography.bodySmall,
                    )
                    TextButton(onClick = {
                        permissionLauncher.launch(HeartRateMonitor.requiredPermissions())
                    }) {
                        Text(stringResource(R.string.heart_rate_grant_permission))
                    }
                } else if (!HeartRateMonitor.isBluetoothEnabled(context)) {
                    Text(
                        text = stringResource(R.string.heart_rate_bluetooth_off),
                        style = MaterialTheme.typography.bodySmall,
                    )
                } else if (!state.connected && !state.connecting) {
                    if (lastDevice != null && state.discovered.none { it.address == lastDevice.second }) {
                        ListItem(
                            headlineContent = {
                                Text(stringResource(R.string.heart_rate_last_device, lastDevice.first))
                            },
                            supportingContent = { Text(lastDevice.second) },
                            trailingContent = { Text(stringResource(R.string.heart_rate_connect)) },
                            colors = ListItemDefaults.colors(
                                containerColor = MaterialTheme.colorScheme.surfaceContainer
                            ),
                            modifier = Modifier
                                .clip(MaterialTheme.shapes.large)
                                .clickable {
                                    HeartRateMonitor.connect(context, lastDevice.second, lastDevice.first)
                                },
                        )
                    }
                    if (state.discovered.isEmpty()) {
                        Text(
                            text = stringResource(
                                if (state.scanning) {
                                    R.string.heart_rate_scanning
                                } else {
                                    R.string.heart_rate_no_devices
                                }
                            ),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else {
                        LazyColumn(
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(max = 240.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            items(state.discovered, key = { it.address }) { device ->
                                ListItem(
                                    headlineContent = { Text(device.name) },
                                    supportingContent = { Text(device.address) },
                                    colors = ListItemDefaults.colors(
                                        containerColor = MaterialTheme.colorScheme.surfaceContainer
                                    ),
                                    modifier = Modifier
                                        .clip(MaterialTheme.shapes.large)
                                        .clickable {
                                            HeartRateMonitor.connect(context, device.address, device.name)
                                        },
                                )
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                if (state.connected || state.connecting) {
                    TextButton(onClick = { HeartRateMonitor.disconnect() }) {
                        Text(stringResource(R.string.heart_rate_disconnect))
                    }
                }
                if (hasPermission && !state.connected && !state.connecting) {
                    TextButton(onClick = {
                        if (state.scanning) {
                            HeartRateMonitor.stopScan(context)
                        } else {
                            HeartRateMonitor.startScan(context)
                        }
                    }) {
                        Text(
                            stringResource(
                                if (state.scanning) {
                                    R.string.heart_rate_stop_scan
                                } else {
                                    R.string.heart_rate_scan
                                }
                            )
                        )
                    }
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.heart_rate_close))
            }
        },
    )
}
