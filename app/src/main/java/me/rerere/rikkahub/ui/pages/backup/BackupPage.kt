package me.rerere.rikkahub.ui.pages.backup

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material3.CircularWavyProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LargeFlexibleTopAppBar
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SecondaryScrollableTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import me.rerere.rikkahub.R
import me.rerere.rikkahub.ui.components.nav.BackButton
import androidx.compose.runtime.LaunchedEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.dokar.sonner.ToastType
import me.rerere.rikkahub.ui.context.LocalToaster
import me.rerere.rikkahub.ui.pages.backup.components.BackupDialog
import androidx.compose.material3.AlertDialog
import me.rerere.rikkahub.ui.pages.backup.tabs.ImportExportTab
import me.rerere.rikkahub.ui.pages.backup.tabs.ReminderTab
import me.rerere.rikkahub.ui.pages.backup.tabs.S3Tab
import me.rerere.rikkahub.ui.pages.backup.tabs.WebDavTab
import me.rerere.rikkahub.ui.theme.CustomColors
import org.koin.androidx.compose.koinViewModel

@Composable
fun BackupPage(vm: BackupVM = koinViewModel()) {
    val pagerState = rememberPagerState { 4 }
    val scope = rememberCoroutineScope()
    var showRestartDialog by remember { mutableStateOf(false) }
    val toaster = LocalToaster.current
    val scrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()

    Scaffold(
        topBar = {
            LargeFlexibleTopAppBar(
                title = {
                    Text(stringResource(R.string.backup_page_title))
                },
                navigationIcon = {
                    BackButton()
                },
                scrollBehavior = scrollBehavior,
                colors = CustomColors.topBarColors
            )
        },
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        containerColor = CustomColors.topBarColors.containerColor
    ) { contentPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(contentPadding)
        ) {
            SecondaryScrollableTabRow(
                selectedTabIndex = pagerState.currentPage,
                containerColor = CustomColors.topBarColors.containerColor,
                edgePadding = 4.dp,
            ) {
                Tab(
                    selected = pagerState.currentPage == 0,
                    onClick = { scope.launch { pagerState.animateScrollToPage(0) } },
                    text = { Text(stringResource(R.string.backup_page_webdav_backup)) }
                )
                Tab(
                    selected = pagerState.currentPage == 1,
                    onClick = { scope.launch { pagerState.animateScrollToPage(1) } },
                    text = { Text(stringResource(R.string.backup_page_s3_backup)) }
                )
                Tab(
                    selected = pagerState.currentPage == 2,
                    onClick = { scope.launch { pagerState.animateScrollToPage(2) } },
                    text = { Text(stringResource(R.string.backup_page_import_export)) }
                )
                Tab(
                    selected = pagerState.currentPage == 3,
                    onClick = { scope.launch { pagerState.animateScrollToPage(3) } },
                    text = { Text(stringResource(R.string.backup_page_reminder)) }
                )
            }

            HorizontalPager(
                state = pagerState,
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
            ) { page ->
                when (page) {
                    0 -> {
                        WebDavTab(
                            vm = vm,
                            onShowRestartDialog = { showRestartDialog = true }
                        )
                    }

                    1 -> {
                        S3Tab(
                            vm = vm,
                            onShowRestartDialog = { showRestartDialog = true }
                        )
                    }

                    2 -> {
                        ImportExportTab(
                            vm = vm,
                            onShowRestartDialog = { showRestartDialog = true }
                        )
                    }

                    3 -> {
                        ReminderTab(vm = vm)
                    }
                }
            }
        }
    }

    // [batch158] 两阶段合并：差异确认对话框 + 结果处理
    val mergeState by vm.mergeUiState.collectAsStateWithLifecycle()
    LaunchedEffect(mergeState) {
        when (val state = mergeState) {
            is BackupVM.MergeUiState.Done -> {
                toaster.show("合并完成：" + state.summary, type = ToastType.Success)
                vm.cancelMerge()
                showRestartDialog = true
            }
            is BackupVM.MergeUiState.Failed -> {
                toaster.show("合并失败：" + state.message, type = ToastType.Error)
                vm.cancelMerge()
            }
            else -> Unit
        }
    }
    (mergeState as? BackupVM.MergeUiState.AwaitingDecision)?.let { state ->
        MergeConfirmDialog(
            plan = state.plan,
            onConversationDecision = vm::updateConversationDecision,
            onSettingsItemDecision = vm::updateSettingsItemDecision,
            onToggleScalar = vm::toggleScalarAdoption,
            onApplyAllBackup = vm::mergeAllUseBackup, // rhMergeBulk
            onKeepAllLocal = vm::mergeAllKeepLocal, // rhMergeBulk
            onConfirm = { vm.confirmMerge() },
            onCancel = { vm.cancelMerge() },
        )
    }

// rhMergeProgress249: 与导入/导出备份包一致的进度样式（波浪进度环 + 当前事项 + 百分比）
val mergeProgress by vm.progress.collectAsStateWithLifecycle()
if (mergeState is BackupVM.MergeUiState.Preparing || mergeState is BackupVM.MergeUiState.Applying) {
    val isApplying = mergeState is BackupVM.MergeUiState.Applying
    AlertDialog(
        onDismissRequest = { },
        icon = { CircularWavyProgressIndicator(modifier = Modifier.size(28.dp)) },
        title = { Text(if (isApplying) "正在应用合并…" else "正在扫描备份差异…") },
        text = {
            val p = mergeProgress
            Text(
                if (p == null) {
                    "请稍候，正在处理备份文件…"
                } else {
                    (if (p.detail.isNotBlank()) p.detail else p.phase) +
                        (p.percent?.let { " " + it + "%" } ?: "")
                }
            )
        },
        confirmButton = { },
    )
}

    if (showRestartDialog) {
        BackupDialog()
    }
}
