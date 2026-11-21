package me.rerere.rikkahub.ui.pages.setting

import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Icon
import androidx.compose.material3.LargeFlexibleTopAppBar
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.SmartPhone01
import me.rerere.rikkahub.ui.components.nav.BackButton
import me.rerere.rikkahub.ui.components.ui.CardGroup
import me.rerere.rikkahub.ui.components.ui.Select
import me.rerere.rikkahub.ui.theme.CustomColors
import me.rerere.rikkahub.utils.plus
import me.rerere.rikkahub.utils.plus // rhPhone348d

/**
 * rhPhone348b -- 手机操控设置页。
 *
 * 信息架构照 dsh-go 的 PhoneControlScreen：顶部状态卡、完成设置、确认方式、
 * 解除限制、高级、页脚。视觉落在 RikkaHub 的 CardGroup 规范上。
 *
 * 状态全部来自两个全局 store（PhoneControlStore / PhonePoliciesStore），
 * 不依赖 SettingVM，避免和设置首页的状态互相打架。
 */
@Composable
fun SettingPhoneControlPage() {
    val context = LocalContext.current
    val scrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()

    var enabled by remember {
        mutableStateOf(me.rerere.rikkahub.phone.PhoneControlStore.enabled)
    }
    val a11yConnected by produceState(initialValue = false) {
        while (true) {
            value = me.rerere.rikkahub.phone.PhoneAccessibilityService.connected()
            delay(1000)
        }
    }
    val policies = me.rerere.rikkahub.phone.PhonePoliciesStore.current
    var mode by remember { mutableStateOf(policies.confirmMode) }
    var unlocks by remember { mutableStateOf(policies.unlocks) }

    fun openA11y() {
        runCatching {
            context.startActivity(
                Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        }
    }

    fun openAppDetails() {
        runCatching {
            context.startActivity(
                Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                    .setData(android.net.Uri.parse("package:" + context.packageName))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        }
    }

    val statusLine = when {
        !enabled -> "未开启 · AI 看不到也动不了这台手机"
        !a11yConnected -> "需要无障碍服务 · 点下面的步骤 1 开启"
        else -> "已就绪 · 读屏、点击、输入都可用"
    }

    Scaffold(
        topBar = {
            LargeFlexibleTopAppBar(
                title = { Text("手机操控") },
                navigationIcon = { BackButton() },
                scrollBehavior = scrollBehavior,
                colors = CustomColors.topBarColors,
            )
        },
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        containerColor = CustomColors.topBarColors.containerColor,
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = innerPadding + PaddingValues(8.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            if (enabled && !a11yConnected) {
                item("phoneBlocker") {
                    CardGroup(
                        modifier = Modifier.padding(horizontal = 8.dp),
                        title = { Text("需要处理") },
                    ) {
                        item(
                            headlineContent = { Text("无障碍服务没有连接") },
                            supportingContent = { Text("手机操控靠它读屏和点按。点这里去系统设置，找到「手机操控」并开启。") },
                            onClick = { openA11y() },
                        )
                    }
                }
            }

            item("phoneOverview") {
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                    title = { Text("总开关") },
                ) {
                    item(
                        leadingContent = { Icon(HugeIcons.SmartPhone01, null) },
                        headlineContent = { Text("手机操控") },
                        supportingContent = { Text(statusLine) },
                        trailingContent = {
                            Switch(
                                checked = enabled,
                                onCheckedChange = { next ->
                                    enabled = next
                                    me.rerere.rikkahub.phone.PhoneControlStore.set(context, next)
                                    if (next && !me.rerere.rikkahub.phone.PhoneAccessibilityService.connected()) {
                                        openA11y()
                                    }
                                }
                            )
                        },
                    )
                }
            }

            item("phoneSetup") {
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                    title = { Text("完成设置") },
                ) {
                    item(
                        headlineContent = { Text("1 · 无障碍服务") },
                        supportingContent = {
                            Text(if (a11yConnected) "已连接" else "未开启 · 点这一行去系统设置")
                        },
                        trailingContent = {
                            Text(
                                if (a11yConnected) "✓" else "去开启",
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.primary,
                            )
                        },
                        onClick = { openA11y() },
                    )
                    item(
                        headlineContent = { Text("2 · 通知") },
                        supportingContent = { Text("没有悬浮确认条时，用通知向你确认敏感操作") },
                        trailingContent = {
                            Text(
                                "去设置",
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.primary,
                            )
                        },
                        onClick = { openAppDetails() },
                    )
                }
            }

            if (unlocks.any) {
                item("phoneUnlocked") {
                    CardGroup(
                        modifier = Modifier.padding(horizontal = 8.dp),
                        title = { Text("已解除限制") },
                    ) {
                        item(
                            headlineContent = { Text("已解除 " + listOf(unlocks.systemPages, unlocks.secretFields, unlocks.ownApp).count { it } + " 项硬规则") },
                            supportingContent = { Text("这些项不再被安全门拦截，风险自负") },
                        )
                    }
                }
            }

            item("phoneRules") {
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                    title = { Text("确认方式") },
                ) {
                    item(
                        headlineContent = { Text("写操作的确认") },
                        supportingContent = { Text("每次都问 / 本任务只问一次 / 始终免确认") },
                        trailingContent = {
                            Select(
                                options = me.rerere.rikkahub.phone.ConfirmMode.entries,
                                selectedOption = mode,
                                onOptionSelected = { next ->
                                    mode = next
                                    me.rerere.rikkahub.phone.PhonePoliciesStore.setConfirmMode(context, next)
                                },
                                optionToString = { m ->
                                    when (m) {
                                        me.rerere.rikkahub.phone.ConfirmMode.ASK -> "每次都问"
                                        me.rerere.rikkahub.phone.ConfirmMode.TASK -> "本任务免确认"
                                        me.rerere.rikkahub.phone.ConfirmMode.ALWAYS -> "始终免确认"
                                    }
                                },
                                modifier = Modifier.padding(start = 8.dp),
                            )
                        },
                    )
                    item(
                        headlineContent = { Text("允许操作系统设置") },
                        supportingContent = { Text("默认关闭 · 设置/权限/安装器页面可点，风险自负") },
                        trailingContent = {
                            Switch(
                                checked = unlocks.systemPages,
                                onCheckedChange = { v ->
                                    unlocks = unlocks.copy(systemPages = v)
                                    me.rerere.rikkahub.phone.PhonePoliciesStore.setUnlock(context, "system", v)
                                }
                            )
                        },
                    )
                    item(
                        headlineContent = { Text("允许填写密码/验证码") },
                        supportingContent = { Text("默认关闭 · 打开后输入内容会进上下文，日志仍遮罩") },
                        trailingContent = {
                            Switch(
                                checked = unlocks.secretFields,
                                onCheckedChange = { v ->
                                    unlocks = unlocks.copy(secretFields = v)
                                    me.rerere.rikkahub.phone.PhonePoliciesStore.setUnlock(context, "secret", v)
                                }
                            )
                        },
                    )
                    item(
                        headlineContent = { Text("允许操作 RikkaHub 自己") },
                        supportingContent = { Text("默认关闭 · 防止 AI 点自己的确认按钮绕过审批") },
                        trailingContent = {
                            Switch(
                                checked = unlocks.ownApp,
                                onCheckedChange = { v ->
                                    unlocks = unlocks.copy(ownApp = v)
                                    me.rerere.rikkahub.phone.PhonePoliciesStore.setUnlock(context, "own", v)
                                }
                            )
                        },
                    )
                }
            }

            item("phoneAdvanced") {
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                    title = { Text("高级") },
                ) {
                    item(
                        headlineContent = { Text("不打扰模式") },
                        supportingContent = { Text("任务在独立屏幕里跑，不占用你正在用的界面（M4，未实现）") },
                    )
                    item(
                        headlineContent = { Text("保持后台运行") },
                        supportingContent = { Text("关掉电池优化，避免系统在任务中途冻结 RikkaHub") },
                        onClick = {
                            runCatching {
                                context.startActivity(
                                    Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)
                                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                )
                            }
                        },
                    )
                    item(
                        headlineContent = { Text("后台弹出界面") },
                        supportingContent = { Text("部分 ROM（vivo/小米）需要它才能在后台启动无障碍确认") },
                        onClick = { openAppDetails() },
                    )
                }
            }

            item("phoneFooter") {
                Column(modifier = Modifier.padding(horizontal = 24.dp)) {
                    Text(
                        "敏感动作（发送、支付、删除、授权）和每个新 App 的第一步都会先问你；银行、支付、券商类 App 既不读也不点。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}
