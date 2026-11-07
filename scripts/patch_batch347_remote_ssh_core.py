#!/usr/bin/env python3
# rhRemote347: SSH 连接内核 (Config / Connection / Pool / Shell) + JSch 依赖 + R8 keep
# 本批只新增文件与依赖, 不接线到 UI/仓库, 因此不影响现有功能。
# 跳板机留到后续批次单独加, 避免一次改动面过大。
import os

MARK = "rhRemote347"
DIAG = "ci_diag_batch347_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())


def log(msg):
    print(msg)


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


SSH_CONFIG = r'''package me.rerere.workspace.ssh

import kotlinx.serialization.Serializable
import java.io.IOException
import java.security.MessageDigest
import java.util.Base64

enum class SshAuthType {
    PASSWORD,
    PRIVATE_KEY,
}

/** 已信任的主机公钥 */
@Serializable
data class SshHostKey(
    /** 算法名, 如 ssh-ed25519 */
    val type: String,
    /** Base64 编码的公钥 blob */
    val key: String,
) {
    /** OpenSSH 风格的 SHA256 指纹 */
    val fingerprint: String
        get() {
            val digest = MessageDigest.getInstance("SHA-256").digest(Base64.getDecoder().decode(key))
            return "SHA256:" + Base64.getEncoder().withoutPadding().encodeToString(digest)
        }
}

data class SshConnectionConfig(
    val host: String,
    val port: Int = 22,
    val username: String,
    val authType: SshAuthType,
    val password: String? = null,
    /** OpenSSH / PEM 格式的私钥文本 */
    val privateKey: String? = null,
    val passphrase: String? = null,
    /** 远程工作目录, 必须是绝对路径 */
    val remoteDir: String,
    /** 为 null 时首次连接会抛出 [SshUnknownHostKeyException], 由用户确认指纹后再连 */
    val hostKey: SshHostKey? = null,
) {
    val address: String
        get() = "$username@$host:$port"

    // 不让凭据出现在日志和异常信息里
    override fun toString(): String =
        "SshConnectionConfig(address=$address, authType=$authType, remoteDir=$remoteDir, " +
            "hostKey=${hostKey?.fingerprint})"
}

/** 测试连接的结果 */
data class SshProbeResult(
    val hostKey: SshHostKey,
    val homeDir: String,
    val shell: String,
    val remoteDirExists: Boolean,
)

/** 服务器的主机密钥尚未被信任, 需要用户确认 [hostKey] 的指纹 */
class SshUnknownHostKeyException(val hostKey: SshHostKey) :
    IOException("Unknown SSH host key ${hostKey.type} ${hostKey.fingerprint}")

/** 服务器的主机密钥与已信任的不一致, 可能遭遇中间人攻击, 也可能是服务器重装过 */
class SshHostKeyChangedException(val expected: SshHostKey, val actual: SshHostKey) :
    IOException("SSH host key changed: expected ${expected.fingerprint}, got ${actual.type} ${actual.fingerprint}")
'''

SSH_CONNECTION = r'''package me.rerere.workspace.ssh

import com.jcraft.jsch.Channel
import com.jcraft.jsch.ChannelExec
import com.jcraft.jsch.ChannelSftp
import com.jcraft.jsch.HostKey
import com.jcraft.jsch.HostKeyRepository
import com.jcraft.jsch.JSch
import com.jcraft.jsch.JSchException
import com.jcraft.jsch.Session
import com.jcraft.jsch.SftpException
import com.jcraft.jsch.UIKeyboardInteractive
import com.jcraft.jsch.UserInfo
import me.rerere.workspace.WorkspaceCommandResult
import java.io.Closeable
import java.io.IOException
import java.io.InputStream
import java.io.InterruptedIOException
import java.io.OutputStream
import java.net.SocketTimeoutException
import java.util.Base64
import java.util.concurrent.CompletableFuture
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ExecutionException
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.locks.ReentrantLock

/**
 * 一条 SSH 连接: 命令走 exec channel, 文件操作复用同一个 SFTP channel。
 *
 * Session 本身允许并发开多个 channel; SFTP channel 不是线程安全的, 由 [sftp] 串行化。
 * 阻塞操作响应线程中断, 调用方可以用中断取消卡在网络上的操作。
 */
internal class SshConnection private constructor(
    val config: SshConnectionConfig,
    private val session: Session,
    val hostKey: SshHostKey,
    private val channelTimeoutMillis: Int,
) : Closeable {
    private val sftpLock = ReentrantLock()
    private var sftpChannel: ChannelSftp? = null
    private val ensuredDirs = ConcurrentHashMap.newKeySet<String>()

    val isConnected: Boolean
        get() = session.isConnected

    // lazy 在初始化抛异常时不会缓存结果, 连接恢复后下次访问会重新获取
    val homeDir: String by lazy { sftp { it.home } }

    val shell: String by lazy { detectShell() }

    fun <T> sftp(block: (ChannelSftp) -> T): T {
        // 可中断地等锁: 前一个操作卡在网络上时, 被取消的等待方能及时返回
        sftpLock.lockInterruptibly()
        try {
            val channel = sftpChannel?.takeIf { it.isConnected } ?: openSftpChannel().also { sftpChannel = it }
            try {
                return block(channel)
            } catch (e: Exception) {
                // 被打断的请求的回应可能稍后才到, 继续用这个 channel 会读到错位的回应, 关掉下次重开
                if (e.isInterruption()) {
                    channel.disconnect()
                    sftpChannel = null
                }
                throw e
            }
        } finally {
            sftpLock.unlock()
        }
    }

    private fun openSftpChannel(): ChannelSftp {
        val channel = openChannel { session.openChannel("sftp") as ChannelSftp }
        connectChannel(step = { openChannel { channel.connect(channelTimeoutMillis) } }, onAbandoned = channel::disconnect)
        return channel
    }

    /**
     * 在后台连接 channel, 被取消时放弃等待: 之后连上了就用 [onAbandoned] 关掉 channel; 失败了则断开整条连接。
     * 失败时 JSch 不会给服务器发 channel close, 远端 channel 可能已经开着。
     */
    private fun connectChannel(step: () -> Unit, onAbandoned: () -> Unit) {
        awaitInterruptibly(step, onAbandoned = { onAbandoned() }, onAbandonedFailure = ::close)
    }

    /** 确保远程目录存在, 每条连接对同一目录只检查一次 */
    fun ensureDir(dir: String) {
        if (dir in ensuredDirs) return
        sftp { it.mkdirs(dir) }
        ensuredDirs += dir
    }

    fun exec(command: String, timeoutMillis: Long, stdin: ByteArray? = null): WorkspaceCommandResult {
        val channel = openChannel { session.openChannel("exec") as ChannelExec }
        channel.setCommand(command)
        // 输入流必须在 connect 之前取, 否则开头的输出会丢
        val stdoutStream = channel.inputStream
        val stderrStream = channel.extInputStream
        channel.connectExec()
        val stdout = SshStreamCollector(stdoutStream)
        val stderr = SshStreamCollector(stderrStream)
        // 没有 stdin 时立即发送 EOF, 避免按 isatty 判断的工具一直等待输入
        val stdinWriter = if (stdin != null) {
            SshStreamWriter(channel.outputStream, stdin)
        } else {
            runCatching { channel.outputStream.close() }
            null
        }
        try {
            val deadline = System.nanoTime() + timeoutMillis * 1_000_000
            while (!channel.isClosed && System.nanoTime() < deadline) {
                Thread.sleep(EXEC_POLL_INTERVAL_MS)
            }
            val finished = channel.isClosed
            if (!finished) {
                channel.kill()
            }
            stdinWriter?.join(1_000)
            stdout.join(1_000)
            stderr.join(1_000)
            return WorkspaceCommandResult(
                exitCode = if (finished) channel.exitStatus else -1,
                stdout = stdout.text(),
                stderr = stderr.text(),
                timedOut = !finished,
                truncated = stdout.truncated || stderr.truncated,
            )
        } catch (e: InterruptedException) {
            // 协程取消时 runInterruptible 会中断这里的等待, 关掉 channel 避免命令继续执行
            channel.kill()
            stdinWriter?.join(1_000)
            stdout.join(1_000)
            stderr.join(1_000)
            throw e
        } finally {
            channel.disconnect()
        }
    }

    /** 在带 PTY 的 exec channel 里运行 [command], [onClose] 在 shell 关闭时调用 */
    fun openShell(command: String, columns: Int, rows: Int, onClose: () -> Unit): SshShell {
        val channel = openChannel { session.openChannel("exec") as ChannelExec }
        channel.setCommand(command)
        channel.setPty(true)
        channel.setPtyType(TERMINAL_TYPE, columns, rows, 0, 0)
        channel.setTerminalMode(TERMINAL_MODES)
        // 输入流必须在 connect 之前取, 否则开头的输出会丢
        val input = channel.inputStream
        val output = channel.outputStream
        channel.connectExec()
        return SshShell(channel, input, output, this, onClose)
    }

    // 不等 SFTP 锁: 断开 session 会关闭所有 channel, 卡住的 SFTP 操作随之失败并释放锁
    override fun close() {
        session.disconnect()
    }

    private inline fun <T> openChannel(block: () -> T): T = try {
        block()
    } catch (e: JSchException) {
        throw SshChannelOpenException(e)
    }

    private fun ChannelExec.connectExec() {
        connectChannel(
            step = {
                try {
                    connect(channelTimeoutMillis)
                } catch (e: JSchException) {
                    // JSch 没有区分这两个阶段的接口, 只能按打开阶段的异常信息判断
                    if (e.message in CHANNEL_OPEN_FAILURE_MESSAGES) throw SshChannelOpenException(e)
                    this@SshConnection.close()
                    throw e
                }
            },
            onAbandoned = { kill() },
        )
    }

    private fun ChannelExec.kill() {
        runCatching { sendSignal("KILL") }
        disconnect()
    }

    private fun detectShell(): String {
        val result = exec("command -v bash", SHELL_DETECT_TIMEOUT_MS)
        // 用户的 rc 文件可能会往 stdout 打印内容, 只认最后一个绝对路径
        val bash = result.stdout.lineSequence().map { it.trim() }.lastOrNull { it.startsWith("/") }
        return if (result.exitCode == 0 && bash != null) bash else "/bin/sh"
    }

    companion object {
        private const val CONNECT_TIMEOUT_MS = 15_000
        const val DEFAULT_CHANNEL_TIMEOUT_MS = 15_000
        private const val KEEPALIVE_INTERVAL_MS = 15_000
        private const val KEEPALIVE_COUNT_MAX = 3
        private const val EXEC_POLL_INTERVAL_MS = 20L
        private const val SHELL_DETECT_TIMEOUT_MS = 15_000L
        private const val TERMINAL_TYPE = "xterm-256color"

        // RFC 4254 的 PTY 模式编码: 开启 IUTF8 (RFC 8160 opcode 42), 以 TTY_OP_END 结尾
        private val TERMINAL_MODES = byteArrayOf(42, 0, 0, 0, 1, 0)

        // Channel.sendChannelOpen 失败时的异常信息, 此时 exec 请求还没发出
        private val CHANNEL_OPEN_FAILURE_MESSAGES = setOf("session is down", "channel is not opened.")

        fun open(config: SshConnectionConfig, channelTimeoutMillis: Int = DEFAULT_CHANNEL_TIMEOUT_MS): SshConnection {
            val jsch = newJSch(config)
            val connected = connectSession(config, jsch)
            return SshConnection(config, connected.session, connected.hostKey, channelTimeoutMillis)
        }

        private fun newJSch(config: SshConnectionConfig): JSch {
            val jsch = JSch()
            when (config.authType) {
                SshAuthType.PASSWORD -> {
                    if (config.password.isNullOrEmpty()) {
                        throw IOException("SSH password is required for ${config.address}")
                    }
                }

                SshAuthType.PRIVATE_KEY -> {
                    val privateKey = config.privateKey?.trim()?.takeIf { it.isNotEmpty() }
                        ?: throw IOException("SSH private key is required for ${config.address}")
                    try {
                        jsch.addIdentity(
                            "rikkahub",
                            "$privateKey\n".toByteArray(),
                            null,
                            config.passphrase?.takeIf { it.isNotEmpty() }?.toByteArray(),
                        )
                    } catch (e: JSchException) {
                        throw IOException("Invalid SSH private key or passphrase for ${config.address}: ${e.message}", e)
                    }
                }
            }
            return jsch
        }

        /** 建立 SSH 会话并完成主机密钥校验和认证 */
        private fun connectSession(config: SshConnectionConfig, jsch: JSch): ConnectedSession {
            val hostKeys = TrustedHostKeyRepository(config.hostKey)
            val session = jsch.getSession(config.username, config.host, config.port).apply {
                setHostKeyRepository(hostKeys)
                setConfig("StrictHostKeyChecking", "yes")
                when (config.authType) {
                    SshAuthType.PASSWORD -> {
                        setConfig("PreferredAuthentications", "password,keyboard-interactive")
                        setPassword(config.password)
                        userInfo = PasswordUserInfo(config.password!!)
                    }

                    SshAuthType.PRIVATE_KEY -> setConfig("PreferredAuthentications", "publickey")
                }
                setServerAliveInterval(KEEPALIVE_INTERVAL_MS)
                serverAliveCountMax = KEEPALIVE_COUNT_MAX
            }
            try {
                session.connect(CONNECT_TIMEOUT_MS)
            } catch (e: JSchException) {
                hostKeys.rejection?.let { throw it }
                throw IOException("SSH connection to ${config.address} failed: ${e.message}", e)
            }
            val hostKey = hostKeys.presented ?: run {
                session.disconnect()
                throw IOException("SSH server ${config.address} did not present a host key")
            }
            return ConnectedSession(session, hostKey)
        }

        /** 用一条临时连接验证配置, 并取回远程环境的基本信息 */
        fun probe(config: SshConnectionConfig): SshProbeResult {
            val connection = awaitInterruptibly({ open(config) }, onAbandoned = { it.close() })
            return connection.use {
                val remoteDir = config.remoteDir.trim()
                SshProbeResult(
                    hostKey = connection.hostKey,
                    homeDir = connection.homeDir,
                    shell = connection.shell,
                    remoteDirExists = remoteDir.startsWith("/") && connection.sftp { sftp ->
                        sftp.statOrNull(remoteDir)?.isDir == true
                    },
                )
            }
        }
    }
}

private class ConnectedSession(val session: Session, val hostKey: SshHostKey)

/** 打开 channel 失败, 请求还没有发到服务器, 重连后重试是安全的 */
internal class SshChannelOpenException(cause: Throwable) : IOException(cause.message, cause)

// JSch 等服务器回应时会吞掉线程中断, 这类步骤放到这里的线程上执行, 见 awaitInterruptibly
private val blockingSteps: ExecutorService = Executors.newCachedThreadPool { runnable ->
    Thread(runnable, "ssh-blocking-step").apply { isDaemon = true }
}

internal fun <T> awaitInterruptibly(
    step: () -> T,
    onAbandoned: (T) -> Unit,
    onAbandonedFailure: () -> Unit = {},
): T {
    if (Thread.interrupted()) throw InterruptedException()
    val future = CompletableFuture.supplyAsync({ step() }, blockingSteps)
    try {
        return future.get()
    } catch (e: ExecutionException) {
        throw e.cause ?: e
    } catch (e: InterruptedException) {
        future.whenComplete { result, error -> if (error == null) onAbandoned(result) else onAbandonedFailure() }
        throw e
    }
}

/** 是否因线程中断而失败: JSch 会把读管道时的 InterruptedIOException 包进 SftpException 等异常里 */
internal fun Throwable.isInterruption(): Boolean = generateSequence(this) { it.cause }.any {
    it is InterruptedException || it is InterruptedIOException && it !is SocketTimeoutException
}

/** 逐级创建目录, 已存在的跳过 */
internal fun ChannelSftp.mkdirs(dir: String) {
    var current = ""
    dir.split('/').filter { it.isNotEmpty() }.forEach { segment ->
        current += "/$segment"
        val attrs = statOrNull(current)
        if (attrs == null) {
            mkdir(current)
        } else if (!attrs.isDir) {
            throw IOException("Not a directory: $current")
        }
    }
}

internal fun ChannelSftp.statOrNull(path: String) = try {
    stat(path.sftpQuote())
} catch (e: SftpException) {
    if (e.id == ChannelSftp.SSH_FX_NO_SUCH_FILE) null else throw e
}

/** JSch 的 stat/ls/get/put/rm/rmdir 会把路径里的 * ? 当通配符展开, 反斜杠转义后按字面处理 */
internal fun String.sftpQuote(): String =
    replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?")

/**
 * 只认用户确认过的那一把主机公钥。校验发生在认证之前,
 * 未知或不一致时连接直接失败, 密码不会发给未经确认的服务器。
 */
private class TrustedHostKeyRepository(private val trusted: SshHostKey?) : HostKeyRepository {
    @Volatile
    var presented: SshHostKey? = null

    @Volatile
    var rejection: IOException? = null

    override fun check(host: String, key: ByteArray): Int {
        val type = runCatching { HostKey(host, key).type }.getOrDefault("unknown")
        val actual = SshHostKey(type = type, key = Base64.getEncoder().encodeToString(key))
        presented = actual
        return when {
            trusted == null -> {
                rejection = SshUnknownHostKeyException(actual)
                HostKeyRepository.NOT_INCLUDED
            }

            trusted.key == actual.key -> {
                rejection = null
                HostKeyRepository.OK
            }

            else -> {
                rejection = SshHostKeyChangedException(trusted, actual)
                HostKeyRepository.CHANGED
            }
        }
    }

    override fun add(hostkey: HostKey, ui: UserInfo?) = Unit

    override fun remove(host: String, type: String) = Unit

    override fun remove(host: String, type: String, key: ByteArray) = Unit

    override fun getKnownHostsRepositoryID(): String = "rikkahub"

    override fun getHostKey(): Array<HostKey> = trustedHostKeys(host = "", type = null)

    // JSch 会把这里返回的算法排到协商列表最前, 保证服务器出示的是已信任的那一类密钥
    override fun getHostKey(host: String?, type: String?): Array<HostKey> = trustedHostKeys(host.orEmpty(), type)

    private fun trustedHostKeys(host: String, type: String?): Array<HostKey> {
        val hostKey = trusted?.let {
            runCatching { HostKey(host, Base64.getDecoder().decode(it.key)) }.getOrNull()
        } ?: return emptyArray()
        return if (type == null || hostKey.type == type) arrayOf(hostKey) else emptyArray()
    }
}

/** 密码认证, 同时应答 keyboard-interactive 的密码提示 */
private class PasswordUserInfo(private val password: String) : UserInfo, UIKeyboardInteractive {
    override fun getPassphrase(): String? = null

    override fun getPassword(): String = password

    override fun promptPassword(message: String?): Boolean = true

    override fun promptPassphrase(message: String?): Boolean = false

    override fun promptYesNo(message: String?): Boolean = false

    override fun showMessage(message: String?) = Unit

    override fun promptKeyboardInteractive(
        destination: String?,
        name: String?,
        instruction: String?,
        prompt: Array<out String>?,
        echo: BooleanArray?,
    ): Array<String> = Array(prompt?.size ?: 0) { password }
}

// 只收集输出, 上限与本地 shell 一致; 超过上限继续读到 EOF 丢弃, 避免管道写满阻塞远端进程
private class SshStreamCollector(
    stream: InputStream,
    private val maxChars: Int = 128 * 1024,
) {
    private val builder = StringBuilder()

    @Volatile
    var truncated = false
        private set

    private val thread = Thread {
        try {
            stream.bufferedReader().use { reader ->
                val buffer = CharArray(4096)
                while (true) {
                    val read = reader.read(buffer)
                    if (read < 0) break
                    synchronized(builder) {
                        val remaining = maxChars - builder.length
                        if (remaining > 0) {
                            builder.append(buffer, 0, minOf(read, remaining))
                        }
                        if (read > remaining) {
                            truncated = true
                        }
                    }
                }
            }
        } catch (_: IOException) {
            // 进程被强杀或连接断开时流会关闭, 保留已读取的内容即可
        }
    }.apply {
        isDaemon = true
        start()
    }

    fun join(millis: Long) = thread.join(millis)

    fun text(): String = synchronized(builder) { builder.toString() }
}

private class SshStreamWriter(
    private val stream: OutputStream,
    private val bytes: ByteArray,
) {
    private val thread = Thread {
        try {
            stream.use { output ->
                output.write(bytes)
                output.flush()
            }
        } catch (_: IOException) {
            // 子进程提前退出或被强杀时 stdin 可能关闭, 忽略即可
        }
    }.apply {
        isDaemon = true
        start()
    }

    fun join(millis: Long) = thread.join(millis)
}
'''

SSH_POOL = r'''package me.rerere.workspace.ssh

import java.io.Closeable
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

/**
 * 按工作区复用 SSH 连接; 配置变化或连接断开时重新连接。
 *
 * 空闲超过 [idleTimeoutMillis] 且没有进行中操作的连接会被关闭, 下次使用时再重连。
 * 清理任务持有连接池本身, 不再使用时必须调用 [close] 停止调度线程并关闭所有连接。
 */
class SshConnectionPool(
    private val idleTimeoutMillis: Long = DEFAULT_IDLE_TIMEOUT_MS,
    sweepIntervalMillis: Long = DEFAULT_SWEEP_INTERVAL_MS,
    /** 打开 channel 并等待请求回应的超时 */
    private val channelTimeoutMillis: Int = SshConnection.DEFAULT_CHANNEL_TIMEOUT_MS,
) : Closeable {
    private val connections = ConcurrentHashMap<String, PooledConnection>()

    // 按工作区串行化建连; 可中断地等待, 前一个建连卡住时被取消的调用方能及时返回
    private val locks = ConcurrentHashMap<String, ReentrantLock>()

    // 关闭与新连接登记共用这把锁: 关闭期间才建好的连接会自行释放, 不会遗留在已关闭的池里
    private val lifecycleLock = Any()

    @Volatile
    private var closed = false
    private val sweeper = Executors.newSingleThreadScheduledExecutor { runnable ->
        Thread(runnable, "ssh-idle-sweeper").apply { isDaemon = true }
    }

    init {
        sweeper.scheduleWithFixedDelay(
            // 定时任务抛异常后不会再被调度, 这里吞掉异常保证后续还能清理
            { runCatching { closeIdle() } },
            sweepIntervalMillis,
            sweepIntervalMillis,
            TimeUnit.MILLISECONDS,
        )
    }

    /** 用一条临时连接测试配置, 不进入连接池 */
    fun probe(config: SshConnectionConfig): SshProbeResult = SshConnection.probe(config)

    fun close(id: String) {
        lockOf(id).withLock {
            connections.remove(id)?.connection?.close()
        }
    }

    /** 停止空闲清理并关闭所有连接, 之后连接池不能再使用 */
    override fun close() {
        val remaining = synchronized(lifecycleLock) {
            if (closed) return
            closed = true
            connections.values.toList().also { connections.clear() }
        }
        sweeper.shutdownNow()
        remaining.forEach { it.connection.close() }
    }

    /**
     * 在 [id] 对应的连接上执行 [block]。连接已断开时重连并重试一次:
     * [retry] 为 true 表示操作可重复执行; 否则只在请求尚未发出 (打开 channel 失败) 时重试。
     */
    internal fun <T> use(
        id: String,
        config: SshConnectionConfig,
        retry: Boolean,
        block: (SshConnection) -> T,
    ): T {
        val pooled = acquire(id, config)
        return try {
            block(pooled.connection)
        } catch (e: Exception) {
            if (e.isInterruption()) throw e
            val channelFailed = e is SshChannelOpenException
            if (pooled.connection.isConnected && !channelFailed) throw e
            evict(id, pooled)
            if (!retry && !channelFailed) throw e
            val retried = acquire(id, config)
            try {
                block(retried.connection)
            } finally {
                retried.release()
            }
        } finally {
            pooled.release()
        }
    }

    /** 在 [id] 对应的连接上打开交互式 shell, shell 关闭前一直占用这条连接 */
    internal fun openShell(
        id: String,
        config: SshConnectionConfig,
        open: (SshConnection, onClose: () -> Unit) -> SshShell,
    ): SshShell {
        val pooled = acquire(id, config)
        return try {
            open(pooled.connection, pooled::release)
        } catch (e: Exception) {
            pooled.release()
            if (e.isInterruption()) throw e
            val channelFailed = e is SshChannelOpenException
            if (pooled.connection.isConnected && !channelFailed) throw e
            evict(id, pooled)
            if (!channelFailed) throw e
            val retried = acquire(id, config)
            try {
                open(retried.connection, retried::release)
            } catch (retryError: Exception) {
                retried.release()
                throw retryError
            }
        }
    }

    /** 连接池里 [id] 是否有可用连接, 供测试观察空闲断开 */
    internal fun isConnected(id: String): Boolean = connections[id]?.connection?.isConnected == true

    // 在锁内登记使用, 清理线程同样持锁检查, 保证拿到手的连接不会被当成空闲关掉
    private fun acquire(id: String, config: SshConnectionConfig): PooledConnection {
        val lock = lockOf(id)
        lock.lockInterruptibly()
        try {
            check(!closed) { "SSH connection pool is closed" }
            connections[id]?.let { existing ->
                if (existing.connection.config == config && existing.connection.isConnected) {
                    existing.retain()
                    return existing
                }
                connections.remove(id)
                existing.connection.close()
            }
            // 被取消时放弃等待, 之后建好的连接直接关掉
            val connection = awaitInterruptibly(
                step = { SshConnection.open(config, channelTimeoutMillis) },
                onAbandoned = { it.close() },
            )
            val pooled = PooledConnection(connection).also { it.retain() }
            synchronized(lifecycleLock) {
                if (!closed) {
                    connections[id] = pooled
                    return pooled
                }
            }
            pooled.connection.close()
            throw IllegalStateException("SSH connection pool is closed")
        } finally {
            lock.unlock()
        }
    }

    private fun evict(id: String, pooled: PooledConnection) {
        lockOf(id).withLock {
            connections.remove(id, pooled)
        }
        pooled.connection.close()
    }

    private fun closeIdle() {
        val now = System.nanoTime()
        connections.forEach { (id, pooled) ->
            lockOf(id).withLock {
                if (connections[id] === pooled && pooled.isIdle(now, idleTimeoutMillis)) {
                    connections.remove(id)
                    pooled.connection.close()
                }
            }
        }
    }

    private fun lockOf(id: String): ReentrantLock = locks.computeIfAbsent(id) { ReentrantLock() }

    private class PooledConnection(val connection: SshConnection) {
        private val activeUses = AtomicInteger()

        @Volatile
        private var lastUsedAt = System.nanoTime()

        fun retain() {
            activeUses.incrementAndGet()
        }

        fun release() {
            lastUsedAt = System.nanoTime()
            activeUses.decrementAndGet()
        }

        fun isIdle(now: Long, timeoutMillis: Long): Boolean =
            activeUses.get() == 0 && now - lastUsedAt >= TimeUnit.MILLISECONDS.toNanos(timeoutMillis)
    }

    private companion object {
        const val DEFAULT_IDLE_TIMEOUT_MS = 5 * 60_000L
        const val DEFAULT_SWEEP_INTERVAL_MS = 30_000L
    }
}
'''

SSH_SHELL = r'''package me.rerere.workspace.ssh

import com.jcraft.jsch.ChannelExec
import java.io.Closeable
import java.io.InputStream
import java.io.OutputStream
import java.util.concurrent.atomic.AtomicBoolean

/**
 * 远程主机上带 PTY 的交互式 shell, 供终端使用。
 *
 * [inputStream] 是 shell 的输出 (PTY 已合并 stderr), [outputStream] 写入 shell 的输入。
 * 打开期间一直占用所在的连接, 不会被连接池当成空闲断开; [close] 后释放。
 */
class SshShell internal constructor(
    private val channel: ChannelExec,
    val inputStream: InputStream,
    val outputStream: OutputStream,
    private val connection: SshConnection,
    private val onClose: () -> Unit,
) : Closeable {
    private val closed = AtomicBoolean(false)

    /** shell 结束时 SSH 连接是否已经断开, 用来区分正常退出和掉线 */
    val connectionLost: Boolean
        get() = !connection.isConnected

    fun resize(columns: Int, rows: Int) {
        channel.setPtySize(columns, rows, 0, 0)
    }

    /** 阻塞到 shell 结束, 返回退出码; 没收到退出码 (掉线、被信号结束或被 [close]) 时返回 null */
    fun waitFor(): Int? {
        while (!channel.isClosed) {
            Thread.sleep(POLL_INTERVAL_MS)
        }
        return channel.exitStatus.takeIf { it >= 0 }
    }

    /** 关闭 channel, 远程 shell 随 PTY 挂断退出 */
    override fun close() {
        if (!closed.compareAndSet(false, true)) return
        try {
            channel.disconnect()
        } finally {
            onClose()
        }
    }

    private companion object {
        const val POLL_INTERVAL_MS = 50L
    }
}
'''


def patch_text(path, edits, diag):
    text = read(path)
    for label, needle, repl in edits:
        if repl in text:
            diag.append(label + ":already")
            continue
        if text.count(needle) != 1:
            diag.append(label + ":ANCHOR-MISMATCH(" + str(text.count(needle)) + ")")
            continue
        text = text.replace(needle, repl, 1)
        diag.append(label + ":ok")
    write(path, text)


def main():
    diag = []
    out = "workspace/src/main/java/me/rerere/workspace/ssh/"
    files = [
        ("SshConfig.kt", SSH_CONFIG),
        ("SshConnection.kt", SSH_CONNECTION),
        ("SshConnectionPool.kt", SSH_POOL),
        ("SshShell.kt", SSH_SHELL),
    ]
    for name, content in files:
        path = out + name
        if os.path.exists(path):
            diag.append(name + ":exists")
            continue
        write(path, content)
        diag.append(name + ":wrote " + str(len(content)))

    # 依赖版本
    ver_edits = [
        (
            "version",
            'diffutils = "4.17"',
            'diffutils = "4.17"\njsch = "2.28.8"',
        ),
    ]
    patch_text("gradle/libs.versions.toml", ver_edits, diag)

    lib_edits = [
        (
            "library",
            'diffutils = { module = "io.github.java-diff-utils:java-diff-utils", version.ref = "diffutils" }',
            'diffutils = { module = "io.github.java-diff-utils:java-diff-utils", version.ref = "diffutils" }\n'
            'jsch = { module = "com.github.mwiede:jsch", version.ref = "jsch" }',
        ),
    ]
    patch_text("gradle/libs.versions.toml", lib_edits, diag)

    ws_edits = [
        (
            "workspace-dep",
            "    implementation(libs.kotlinx.serialization.json)",
            "    implementation(libs.kotlinx.serialization.json)\n    implementation(libs.jsch)",
        ),
    ]
    patch_text("workspace/build.gradle.kts", ws_edits, diag)

    # R8: JSch 通过类名反射加载 cipher/kex/压缩实现, 必须整包保留
    keep = read("app/proguard-rules.pro")
    if "com.jcraft.jsch" not in keep:
        keep += (
            "\n# JSch loads its cipher, key exchange and compression implementations by class name from its config.\n"
            "-keep class com.jcraft.jsch.** { *; }\n"
            "\n# JSch optional integrations (JNA / junixsocket / logging bridges / GSSAPI) are unused on Android.\n"
            "-dontwarn com.sun.jna.**\n"
            "-dontwarn org.newsclub.net.unix.**\n"
            "-dontwarn org.slf4j.**\n"
            "-dontwarn org.apache.logging.log4j.**\n"
            "-dontwarn org.ietf.jgss.**\n"
        )
        write("app/proguard-rules.pro", keep)
        diag.append("proguard:ok")
    else:
        diag.append("proguard:already")

    # 自检: 五个源文件括号必须配平; 依赖行必须存在
    ok = True
    for name, content in files:
        left = content.count("(")
        right = content.count(")")
        if left != right:
            diag.append(name + ":UNBALANCED(" + str(left) + "/" + str(right) + ")")
            ok = False
    toml = read("gradle/libs.versions.toml")
    if "jsch = \"2.28.8\"" not in toml or "com.github.mwiede:jsch" not in toml:
        diag.append("toml:MISS")
        ok = False
    if "libs.jsch" not in read("workspace/build.gradle.kts"):
        diag.append("gradle:MISS")
        ok = False

    diag.append("RESULT:" + ("OK" if ok else "FAIL"))
    with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
        f.write("\n".join(diag) + "\n")
    log(" | ".join(diag))
    if not ok:
        print("::error title=batch347::" + " | ".join(diag))


main()
