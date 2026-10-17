package me.rerere.rikkahub.ui.pages.assistant.detail

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import kotlinx.coroutines.launch
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LargeFlexibleTopAppBar
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.dokar.sonner.ToastType
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.ai.tools.LocalToolOption
import me.rerere.rikkahub.data.ai.tools.local.PermissionHelper
import me.rerere.rikkahub.data.model.Assistant
import me.rerere.rikkahub.ui.components.nav.BackButton
import me.rerere.rikkahub.ui.components.ui.CardGroup
import me.rerere.rikkahub.ui.components.ui.CardGroupScope
import me.rerere.rikkahub.ui.context.LocalToaster
import me.rerere.rikkahub.ui.theme.CustomColors
import me.rerere.rikkahub.utils.writeClipboardText
import org.koin.androidx.compose.koinViewModel
import org.koin.core.parameter.parametersOf

@Composable
fun AssistantLocalToolPage(id: String) {
    val vm: AssistantDetailVM = koinViewModel(
        parameters = {
            parametersOf(id)
        }
    )
    val assistant by vm.assistant.collectAsStateWithLifecycle()
    val scrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()

    Scaffold(
        topBar = {
            LargeFlexibleTopAppBar(
                title = {
                    Text(stringResource(R.string.assistant_page_tab_local_tools))
                },
                navigationIcon = {
                    BackButton()
                },
                scrollBehavior = scrollBehavior,
                colors = CustomColors.topBarColors,
            )
        },
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        containerColor = CustomColors.topBarColors.containerColor,
    ) { innerPadding ->
        AssistantLocalToolContent(
            modifier = Modifier.padding(innerPadding),
            assistant = assistant,
            onUpdate = { vm.update(it) },
            // Transform-based path used by the per-tool toggles. Each tap runs inside
            // SettingsStore.update's mutex against the genuinely-current Assistant, so
            // rapid taps no longer race + clobber each other (was: tap A then B then C
            // could land with only C persisted because each tap snapshotted the same
            // pre-A Assistant from `assistant.value`).
            onUpdateAssistant = { transform -> vm.updateAssistant(transform) },
        )
    }
}

@Composable
private fun AssistantLocalToolContent(
    modifier: Modifier = Modifier,
    assistant: Assistant,
    onUpdate: (Assistant) -> Unit,
    onUpdateAssistant: ((Assistant) -> Assistant) -> Unit,
) {
    fun toggleLocalTool(option: LocalToolOption, enabled: Boolean) {
        // Use the transform path so rapid taps (especially through a permission-grant
        // round-trip to system Settings) all serialise against the actual current state
        // instead of whatever stale snapshot the recomposition was holding.
        onUpdateAssistant { current ->
            current.copy(
                localTools = if (enabled) current.localTools + option
                else current.localTools - option,
            )
        }
    }

    val ctx = LocalContext.current
    val toaster = LocalToaster.current
    val scope = rememberCoroutineScope()
    // Hardware-availability gate for the NFC toggle: a device with no NFC chip can never
    // run the nfc tools, so the toggle is shown disabled with a "no NFC hardware" subtitle
    // rather than letting the user enable a tool that would only ever error.
    val hasNfc = remember {
        ctx.packageManager.hasSystemFeature(android.content.pm.PackageManager.FEATURE_NFC)
    }


    var rhToolQuery by remember { mutableStateOf("") } // rhToolSearch225
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp)
            .verticalScroll(rememberScrollState())
            .imePadding(),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        OutlinedTextField( // rhToolSearchBox225
            value = rhToolQuery,
            onValueChange = { rhToolQuery = it },
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("搜索工具名称") },
            singleLine = true,
        )
        // Built-in tools section
        Text(
            text = stringResource(R.string.assistant_page_local_tools_section_existing),
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(start = 16.dp, top = 8.dp)
        )
        CardGroup {
            rhToolItem(rhToolQuery, "聊天界面皮肤（HTML 模式） 允许 AI 编写 HTML 皮肤，改变聊天背景、气泡和悬浮元素") { // rhToolSearch225
            item(
                headlineContent = { Text("聊天界面皮肤（HTML 模式）") },
                supportingContent = { Text("允许 AI 编写 HTML 皮肤，改变聊天背景、气泡和悬浮元素") },
                trailingContent = {
                    Switch(
                        checked = assistant.localTools.contains(LocalToolOption.ChatUi),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.ChatUi, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "当前使用 HTML 模式 关闭即恢复原生聊天界面；需要先有 AI 写好的皮肤") { // rhToolSearch225
            item(
                headlineContent = { Text("当前使用 HTML 模式") },
                supportingContent = { Text("关闭即恢复原生聊天界面；需要先有 AI 写好的皮肤") },
                trailingContent = {
                    if (me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.isReady) {
                        val skinStore = me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.store
                        val skinState by skinStore.stateFlow.collectAsStateWithLifecycle()
                        Switch(
                            checked = skinState.htmlModeEnabled,
                            onCheckedChange = { skinStore.setMode(it) }
                        )
                    }
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "应用控制（App Control） 允许 AI 读取并修改助手、模型、供应商等设置；每次修改都需要你批准") { // rhToolSearch225
            item(
                headlineContent = { Text("应用控制（App Control）") },
                supportingContent = { Text("允许 AI 读取并修改助手、模型、供应商等设置；每次修改都需要你批准") },
                trailingContent = {
                    Switch(
                        checked = assistant.localTools.contains(LocalToolOption.AppControl),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.AppControl, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "图片创作（AI 生成图片） 允许 AI 调用 generate_image，用图片创作页选的模型生图并存入图库；每次调用都会产生费用") { // rhToolSearch225
            item(
                headlineContent = { Text("图片创作（AI 生成图片）") },
                supportingContent = { Text("允许 AI 调用 generate_image，用图片创作页选的模型生图并存入图库；每次调用都会产生费用") },
                trailingContent = {
                    Switch(
                        checked = assistant.localTools.contains(LocalToolOption.ImageGeneration),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.ImageGeneration, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "子代理（Sub-agents） 分发 AI 任务并获得摘要") { // rhToolSearch225
            item(
                headlineContent = { Text("子代理（Sub-agents）") },
                supportingContent = { Text("分发 AI 任务并获得摘要") },
                trailingContent = {
                    Switch(
                        checked = assistant.localTools.contains(LocalToolOption.SubAgents),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.SubAgents, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "版本查看 允许 AI 查看当前 App 版本号与 CI 构建号") { // rhToolSearch225
            item( // rhAppVersionSwitch225
                headlineContent = { Text("版本查看") },
                supportingContent = { Text("允许 AI 查看当前 App 版本号与 CI 构建号") },
                trailingContent = {
                    Switch(
                        checked = assistant.localTools.contains(LocalToolOption.AppVersion),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.AppVersion, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "JavaScript Engine JavaScript 引擎 Execute JavaScript code with QuickJS engine for calculations and scripting 用 QuickJS 引擎执行 JavaScript 代码，做计算和脚本处理哦") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_javascript_engine_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_javascript_engine_desc))
                },
                trailingContent = {
                    Switch(
                        checked = assistant.localTools.contains(LocalToolOption.JavascriptEngine),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.JavascriptEngine, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Time Info 时间信息 Get current date, weekday, time, and timezone info from the device 从设备获取当前日期、星期、时间和时区信息呀♪") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_time_info_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_time_info_desc))
                },
                trailingContent = {
                    Switch(
                        checked = assistant.localTools.contains(LocalToolOption.TimeInfo),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.TimeInfo, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Clipboard 剪贴板 Read or write plain text from the device clipboard 读取或写入设备剪贴板中的纯文本呀") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_clipboard_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_clipboard_desc))
                },
                trailingContent = {
                    Switch(
                        checked = assistant.localTools.contains(LocalToolOption.Clipboard),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Clipboard, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Text to Speech 文字转语音 Let the AI read text aloud to you using your selected TTS service 让 AI 用你选的 TTS 服务朗读文本哦 ・ω・") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_tts_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_tts_desc))
                },
                trailingContent = {
                    Switch(
                        checked = assistant.localTools.contains(LocalToolOption.Tts),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Tts, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Ask User 询问用户 Allow the AI to ask you questions for clarification 允许 AI 向你提问来获取更多信息哦") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_ask_user_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_ask_user_desc))
                },
                trailingContent = {
                    Switch(
                        checked = assistant.localTools.contains(LocalToolOption.AskUser),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.AskUser, it) }
                    )
                }
            )
            } // rhToolSearch225
        }

        // Device info section
        Text(
            text = stringResource(R.string.assistant_page_local_tools_section_device_info),
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(start = 16.dp, top = 8.dp)
        )
        CardGroup {
            rhToolItem(rhToolQuery, "Battery 电池 Read battery level, charging state, plug type, temperature, and health. 读取电量、充电状态、充电方式、温度和健康度。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_battery_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_battery_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Battery),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Battery, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Audio info 音频信息 Read ringer mode, music-active state, headphone connection, and output devices. 读取响铃模式、音乐播放状态、耳机连接和输出设备。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_audio_info_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_audio_info_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.AudioInfo),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.AudioInfo, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Telephony info 电话信息 Read SIM and network info carrier, network type . Requires READ_PHONE_STATE. 读取 SIM 卡和网络信息（运营商、网络类型）。需要 READ_PHONE_STATE 权限。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_telephony_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_telephony_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.TelephonyInfo),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.TelephonyInfo, it) },
                        requiredRuntimePerms = listOf(Manifest.permission.READ_PHONE_STATE),
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Wi-Fi info Wi-Fi 信息 Read current Wi-Fi connection SSID, IP, signal . Requires location permission for SSID. 读取当前 Wi-Fi 连接（SSID、IP、信号）。读取 SSID 需要位置权限。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_wifi_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_wifi_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.WifiInfo),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.WifiInfo, it) },
                        requiredRuntimePerms = listOf(
                            Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION,
                        ),
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Sensors 传感器 List device sensors and read short samples accelerometer, gyroscope, light, etc. . 列出设备传感器并读取短样本（加速度计、陀螺仪、光线等）。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_sensors_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_sensors_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Sensors),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Sensors, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Storage info 存储信息 Read total/free/used storage on internal and external volumes. 读取内部和外部存储卷的总计/可用/已用空间。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_storage_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_storage_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.StorageInfo),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.StorageInfo, it) }
                    )
                }
            )
            } // rhToolSearch225
        }

        // Output section
        Text(
            text = stringResource(R.string.assistant_page_local_tools_section_output),
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(start = 16.dp, top = 8.dp)
        )
        CardGroup {
            rhToolItem(rhToolQuery, "Toast Toast 提示 Show a brief toast popup over whatever is currently on screen. 在当前屏幕内容上方显示一个简短的 toast 弹窗。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_toast_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_toast_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Toast),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Toast, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "系统通知 允许 AI 主动发送系统通知（状态栏提醒）") { // rhToolSearch225
            item( // rhNotifSwitch (batch96)
                headlineContent = {
                    Text("系统通知")
                },
                supportingContent = {
                    Text("允许 AI 主动发送系统通知（状态栏提醒）")
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Notification),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Notification, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "AI 自定义工具 允许 AI 自己编写 JavaScript 工具并调用（在 设置-高级功能 里管理）") { // rhToolSearch225
            item( // rhCustomToolsRow (batch213)
                headlineContent = {
                    Text("AI 自定义工具")
                },
                supportingContent = {
                    Text("允许 AI 自己编写 JavaScript 工具并调用（在 设置-高级功能 里管理）")
                },
                trailingContent = {
                    Switch(
                        checked = assistant.localTools.contains(LocalToolOption.CustomTools),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.CustomTools, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Share 分享 Open the system share sheet to send text or a URL to other apps. 打开系统分享面板，将文本或网址发送到其他应用。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_share_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_share_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Share),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Share, it) }
                    )
                }
            )
            } // rhToolSearch225
        }

        // Hardware control section
        Text(
            text = stringResource(R.string.assistant_page_local_tools_section_hardware),
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(start = 16.dp, top = 8.dp)
        )
        CardGroup {
            rhToolItem(rhToolQuery, "Torch 手电筒 Turn the camera flashlight on or off. 打开或关闭相机闪光灯。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_torch_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_torch_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Torch),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Torch, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Vibrate 振动 Vibrate the device with a duration or pattern. 按时长或模式让设备振动。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_vibrate_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_vibrate_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Vibrate),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Vibrate, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Brightness 亮度 Read and set screen brightness. Setting requires WRITE_SETTINGS. 读取和设置屏幕亮度。设置需要 WRITE_SETTINGS 权限。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_brightness_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_brightness_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Brightness),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Brightness, it) },
                        requiresWriteSettings = true,
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Volume 音量 Read and set audio stream volumes through the system audio controls. 读取和设置音频流音量。铃声/通知音量流需要勿扰模式访问权限。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_volume_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_volume_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Volume),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Volume, it) },
                    )
                }
            )
            } // rhToolSearch225
        }

        // Personal data section
        Text(
            text = stringResource(R.string.assistant_page_local_tools_section_personal_data),
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(start = 16.dp, top = 8.dp)
        )
        CardGroup {
            rhToolItem(rhToolQuery, "Location 位置 Read the device\\'s current location latitude, longitude, accuracy . 读取设备当前位置（纬度、经度、精度）。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_location_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_location_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Location),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Location, it) },
                        requiredRuntimePerms = listOf(
                            Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION,
                        ),
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Contacts 联系人 Search or list device contacts name, phone numbers, emails . 搜索或列出设备联系人（姓名、电话号码、邮箱）。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_contacts_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_contacts_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Contacts),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Contacts, it) },
                        requiredRuntimePerms = listOf(Manifest.permission.READ_CONTACTS),
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Call log 通话记录 Read recent calls incoming, outgoing, missed with duration and timestamps. 读取最近通话（来电、去电、未接）及其时长和时间戳。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_call_log_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_call_log_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.CallLog),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.CallLog, it) },
                        requiredRuntimePerms = listOf(Manifest.permission.READ_CALL_LOG),
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "SMS inbox 短信收件箱 Read or search SMS inbox messages. 读取或搜索短信收件箱中的消息。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_sms_inbox_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_sms_inbox_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.SmsInbox),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.SmsInbox, it) },
                        requiredRuntimePerms = listOf(Manifest.permission.READ_SMS),
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Camera photo 相机（拍照） Open the system camera so the user can take a photo and return its file path. 打开系统相机，让用户拍照并返回其文件路径。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_camera_photo_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_camera_photo_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.CameraPhoto),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.CameraPhoto, it) },
                        requiredRuntimePerms = listOf(Manifest.permission.CAMERA),
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Mic recorder 麦克风录音 Record audio from the microphone for a bounded duration to a local file. 从麦克风录制限定时长的音频到本地文件。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_mic_recorder_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_mic_recorder_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.MicRecorder),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.MicRecorder, it) },
                        requiredRuntimePerms = listOf(Manifest.permission.RECORD_AUDIO),
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Speech to text 语音转文字 Listen to the microphone and convert spoken words to text. 聆听麦克风并将语音转换为文字。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_speech_to_text_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_speech_to_text_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.SpeechToText),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.SpeechToText, it) },
                        requiredRuntimePerms = listOf(Manifest.permission.RECORD_AUDIO),
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Fingerprint 指纹 Show the system biometric prompt to verify the user\\'s identity. 显示系统生物识别提示以验证用户身份。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_fingerprint_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_fingerprint_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Fingerprint),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Fingerprint, it) },
                        requiredRuntimePerms = listOf(Manifest.permission.USE_BIOMETRIC),
                    )
                }
            )
            } // rhToolSearch225
        }

        // Media section
        Text(
            text = stringResource(R.string.assistant_page_local_tools_section_media),
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(start = 16.dp, top = 8.dp)
        )
        CardGroup {
            rhToolItem(rhToolQuery, "Media player 媒体播放器 Play and stop audio from a file path or URL. 从文件路径或网址播放和停止音频。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_media_player_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_media_player_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.MediaPlayer),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.MediaPlayer, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Media scanner 媒体扫描器 Notify Android\\'s media scanner about new files so they appear in gallery/music apps. 通知 Android 媒体扫描器有新文件，使其出现在图库/音乐应用中。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_media_scanner_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_media_scanner_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.MediaScanner),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.MediaScanner, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Download 下载 Download files from URLs into the public Downloads folder, and save text content notes, transcripts, jokes, scripts as files there. 从网址下载文件到公共下载文件夹，并将文本内容（笔记、转录、笑话、脚本）保存为文件。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_download_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_download_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Download),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Download, it) }
                    )
                }
            )
            } // rhToolSearch225
        }

        Text(
            text = stringResource(R.string.assistant_page_local_tools_section_files),
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(start = 16.dp, top = 8.dp)
        )
        CardGroup {
            rhToolItem(rhToolQuery, "Files 文件 Read, write, list, search, copy, move, delete files. 读取、写入、列出、搜索、复制、移动、删除文件。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_files_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_files_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Files),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Files, it) },
                        // MANAGE_EXTERNAL_STORAGE is a special "appop" permission. Without it,
                        // File.listFiles() on shared storage paths only returns subdirectories
                        // and the app's own creations — every pre-existing file is hidden.
                        requiresAllFilesAccess = true,
                    )
                }
            )
            } // rhToolSearch225
        }

        Text(
            text = stringResource(R.string.assistant_page_local_tools_section_network),
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(start = 16.dp, top = 8.dp)
        )
        CardGroup {
            rhToolItem(rhToolQuery, "MCP control MCP 控制 Allow the assistant to add, edit, and remove MCP servers with in-app configuration and per-action approval. 允许助手添加、编辑和删除 MCP 服务器，并在应用内完成配置与逐次审批。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_mcp_control_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_mcp_control_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.McpControl),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.McpControl, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Cost guards 成本守护 Let the assistant inspect its running token totals against the per-assistant soft / hard caps and self-throttle. Read-only — auto-stop integration with the streaming pipeline ships in a follow-up. 让助手对照每个助手的软/硬上限检查其累计 token 用量并自我限流。只读 — 与流式管道的自动停止集成将在后续版本中提供。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_cost_guards_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_cost_guards_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.CostGuards),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.CostGuards, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Skill import 技能导入 Let the assistant install skills from a URL OR from text it already has e.g. fetched via MCP for authenticated servers . Native, openclaw, and Hermes formats. Per-call approval required for every install Always Allow is disabled — you review the source each time . 让助手从网址或已有的文本安装技能（例如通过 MCP 从需认证的服务器获取）。支持原生、openclaw 和 Hermes 格式。每次安装都需要逐次授权（已禁用“始终允许” — 你每次都要审查来源）。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_skill_import_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_skill_import_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.SkillImport),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.SkillImport, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "JS skills JS 技能 Let the assistant run JavaScript skills calculate hash, query Wikipedia, generate QR codes, render maps, etc. inside a hidden WebView. The skill\\'s code defines what it does; per-call approval each time. Compatible with skills written for Google AI Edge Gallery — drop them into your skills folder and they just work. 让助手在隐藏的 WebView 中运行 JavaScript 技能（计算哈希、查询维基百科、生成二维码、渲染地图等）。技能的代码定义其功能；每次调用都需授权。兼容为 Google AI Edge Gallery 编写的技能 — 把它们放进你的技能文件夹即可使用。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_js_skills_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_js_skills_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.JsSkills),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.JsSkills, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "System intents 系统 Intent Let the assistant pre-fill system apps for you to finalise: Calendar event, new Contact, email composer, SMS composer, WiFi settings, Maps. Nothing is saved or sent without your tap in the destination app. 让助手为你预填系统应用，由你最终确认：日历事件、新建联系人、邮件编辑器、短信编辑器、WiFi 设置、地图。没有你在目标应用中的点击，不会保存或发送任何内容。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_system_intents_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_system_intents_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.SystemIntents),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.SystemIntents, it) }
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "OrangeChat 生活工具 日历读写、闹钟、计时器、应用使用统计和媒体控制；所有有副作用的操作仍需授权。") { // rhToolSearch225
            item(
                headlineContent = { Text("OrangeChat 生活工具") },
                supportingContent = {
                    Text("日历读写、闹钟、计时器、应用使用统计和媒体控制；所有有副作用的操作仍需授权。")
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.OrangeChat),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.OrangeChat, it) },
                        requiredRuntimePerms = listOf(
                            Manifest.permission.READ_CALENDAR,
                            Manifest.permission.WRITE_CALENDAR,
                        ),
                        requiresUsageAccess = true,
                    )
                },
            )
            } // rhToolSearch225
        }

        Text(
            text = stringResource(R.string.assistant_page_local_tools_section_browser),
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(start = 16.dp, top = 8.dp)
        )
        CardGroup {
            rhToolItem(rhToolQuery, "Browser 浏览器 AI-driven web browser. 17 individually-togglable tools — configure read/write access in Settings → Browser. AI 驱动的网页浏览器。17 个可单独开关的工具 — 在 设置 → 浏览器 中配置读/写访问权限。") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_browser_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_browser_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Browser),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Browser, it) },
                    )
                }
            )
            } // rhToolSearch225
        }

        // Phase 25 — Phase 3 second cut + ExternalStorage + Archive.
        Text(
            text = stringResource(R.string.assistant_page_local_tools_section_privileged),
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(start = 16.dp, top = 8.dp)
        )
        CardGroup {
            rhToolItem(rhToolQuery, "SMS send Send SMS messages programmatically. Requires SEND_SMS permission. Approval required per call.") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_sms_send_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_sms_send_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.SmsSend),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.SmsSend, it) },
                        requiredRuntimePerms = listOf(Manifest.permission.SEND_SMS),
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Wallpaper Set the home or lock screen wallpaper from a local image. Approval required per call.") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_wallpaper_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_wallpaper_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Wallpaper),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Wallpaper, it) },
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Keystore Generate, sign, encrypt, and decrypt with hardware-backed keys Android Keystore . 7 tools.") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_keystore_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_keystore_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Keystore),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Keystore, it) },
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "NFC Read and write NDEF records on NFC tags. Requires the app to be in foreground for tag detection. This device has no NFC hardware, so these tools cannot be enabled.") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_nfc_title))
                },
                supportingContent = {
                    Text(
                        if (hasNfc) stringResource(R.string.assistant_page_local_tools_nfc_desc)
                        else stringResource(R.string.assistant_page_local_tools_nfc_unavailable)
                    )
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = hasNfc && assistant.localTools.contains(LocalToolOption.Nfc),
                        // Guard the callback too: even if the switch is somehow toggled,
                        // a device with no NFC chip never gets the tool enabled.
                        onCheckedChange = { if (hasNfc) toggleLocalTool(LocalToolOption.Nfc, it) },
                        enabled = hasNfc,
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "External storage Lets file tools work on USB drives, SD cards, Downloads, and cloud storage. Each tree requires a one-time grant via the SAF picker.") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_external_storage_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_external_storage_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.ExternalStorage),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.ExternalStorage, it) },
                    )
                }
            )
            } // rhToolSearch225
            rhToolItem(rhToolQuery, "Archive zip Create and extract .zip archives directly. No password support in v1. Works on file:// and content:// URIs.") { // rhToolSearch225
            item(
                headlineContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_archive_title))
                },
                supportingContent = {
                    Text(stringResource(R.string.assistant_page_local_tools_archive_desc))
                },
                trailingContent = {
                    PermissionedSwitch(
                        checked = assistant.localTools.contains(LocalToolOption.Archive),
                        onCheckedChange = { toggleLocalTool(LocalToolOption.Archive, it) },
                    )
                }
            )
            } // rhToolSearch225
        }

    }
}

// [batch225] rhToolSearch225: 搜索过滤行包装。query 为空显示全部;
// 否则只显示名称或描述 key 命中的行。包装不改变块内任何逻辑。
private fun CardGroupScope.rhToolItem(query: String, key: String, block: CardGroupScope.() -> Unit) {
    if (query.isBlank() || key.contains(query.trim(), ignoreCase = true)) {
        block()
    }
}

@Composable
private fun PermissionedSwitch(
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    requiredRuntimePerms: List<String> = emptyList(),
    requiresWriteSettings: Boolean = false,
    requiresAllFilesAccess: Boolean = false,
    requiresUsageAccess: Boolean = false,
    enabled: Boolean = true,
) {
    val ctx = LocalContext.current
    val toaster = LocalToaster.current
    val deniedToastFmt = stringResource(R.string.assistant_page_local_tools_perm_denied_toast)

    var showDialog by remember { mutableStateOf(false) }
    var pendingSpecialResume by remember { mutableStateOf(false) }
    // Bumped on ON_RESUME so permissionMissing recomputes when the user returns from settings.
    var resumeTrigger by remember { mutableStateOf(0) }

    // Runtime permission launcher
    val runtimePermLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        val denied = results.filter { !it.value }.keys
        if (denied.isEmpty()) {
            if (requiresUsageAccess && !PermissionHelper.hasUsageAccess(ctx)) {
                showDialog = true
            } else {
                onCheckedChange(true)
            }
        } else {
            toaster.show(
                message = String.format(deniedToastFmt, denied.joinToString(", ")),
                type = ToastType.Error,
            )
        }
    }

    // Special permission settings launcher
    val specialPermLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) {
        // result is ignored — actual check happens on ON_RESUME
    }

    // Lifecycle observer: handles both special-perm resume and re-evaluating
    // the permissionMissing hint when the user returns from settings.
    // Keyed on lifecycleOwner only — the closure reads other state, so re-installing
    // on every state change would be wasteful (and was a measured perf bug across the
    // ~30 PermissionedSwitch instances rendered on this screen).
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                resumeTrigger++
                if (pendingSpecialResume) {
                    val granted = when {
                        requiresWriteSettings -> PermissionHelper.hasWriteSettings(ctx)
                        requiresAllFilesAccess -> PermissionHelper.hasAllFilesAccess(ctx)
                        requiresUsageAccess -> PermissionHelper.hasUsageAccess(ctx)
                        else -> false
                    }
                    pendingSpecialResume = false
                    if (granted) {
                        onCheckedChange(true)
                    } else {
                        val name = when {
                            requiresWriteSettings -> "WRITE_SETTINGS"
                            requiresAllFilesAccess -> "All files access"
                            requiresUsageAccess -> "Usage access"
                            else -> ""
                        }
                        toaster.show(
                            message = String.format(deniedToastFmt, name),
                            type = ToastType.Error,
                        )
                    }
                }
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    fun requestPermission() {
        when {
            requiresWriteSettings -> {
                if (PermissionHelper.hasWriteSettings(ctx)) {
                    onCheckedChange(true)
                } else {
                    showDialog = true
                }
            }

            requiresAllFilesAccess -> {
                if (PermissionHelper.hasAllFilesAccess(ctx)) {
                    onCheckedChange(true)
                } else {
                    showDialog = true
                }
            }

            requiredRuntimePerms.isNotEmpty() && !PermissionHelper.hasRuntime(ctx, requiredRuntimePerms) -> {
                runtimePermLauncher.launch(requiredRuntimePerms.toTypedArray())
            }

            requiresUsageAccess && !PermissionHelper.hasUsageAccess(ctx) -> {
                showDialog = true
            }

            else -> onCheckedChange(true)
        }
    }

    // Recomputed each ON_RESUME via resumeTrigger so the hint reflects any
    // permissions the user toggled in system settings while we were paused.
    // Key on a stable string derived from the perms list — Compose can't compare
    // raw List<String> for structural equality across recomps, so passing the list
    // directly invalidated this remember on every parent recomp.
    val permsKey = remember(requiredRuntimePerms) { requiredRuntimePerms.joinToString(",") }
    val permissionMissing = remember(
        checked,
        resumeTrigger,
        permsKey,
        requiresWriteSettings,
        requiresAllFilesAccess,
        requiresUsageAccess,
    ) {
        checked && when {
            requiredRuntimePerms.isNotEmpty() -> !PermissionHelper.hasRuntime(ctx, requiredRuntimePerms) ||
                (requiresUsageAccess && !PermissionHelper.hasUsageAccess(ctx))
            requiresWriteSettings -> !PermissionHelper.hasWriteSettings(ctx)
            requiresAllFilesAccess -> !PermissionHelper.hasAllFilesAccess(ctx)
            requiresUsageAccess -> !PermissionHelper.hasUsageAccess(ctx)
            else -> false
        }
    }

    if (showDialog) {
        AlertDialog(
            onDismissRequest = { showDialog = false },
            title = {
                Text(stringResource(R.string.assistant_page_local_tools_perm_special_dialog_title))
            },
            text = {
                Text(stringResource(R.string.assistant_page_local_tools_perm_special_dialog_message))
            },
            confirmButton = {
                TextButton(onClick = {
                    showDialog = false
                    val intent = when {
                        requiresWriteSettings -> PermissionHelper.writeSettingsIntent(ctx)
                        requiresAllFilesAccess -> PermissionHelper.allFilesAccessIntent(ctx)
                        requiresUsageAccess -> PermissionHelper.usageAccessIntent()
                        else -> null
                    }
                    if (intent != null) {
                        pendingSpecialResume = true
                        specialPermLauncher.launch(intent)
                    }
                }) {
                    Text(stringResource(android.R.string.ok))
                }
            },
            dismissButton = {
                TextButton(onClick = { showDialog = false }) {
                    Text(stringResource(android.R.string.cancel))
                }
            }
        )
    }

    Column(horizontalAlignment = Alignment.End) {
        Switch(
            checked = checked,
            enabled = enabled,
            onCheckedChange = { newChecked ->
                if (!newChecked) {
                    onCheckedChange(false)
                    return@Switch
                }
                // Turning ON
                requestPermission()
            }
        )
        if (permissionMissing) {
            Text(
                text = stringResource(R.string.assistant_page_local_tools_perm_needed),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.clickable { requestPermission() },
            )
        }
    }
}

