#!/usr/bin/env python3
# rhRemote356a: 跳板机数据层 (Config + Settings + Repository 解密)
# v2 修复: v1 的 os.getcwd__ 双下划线笔误导致 import 即崩, patch 链在此中断。
# SshConnectionConfig.jumpHost 字段暂无人消费(356b 接线), 本批可独立编译。
import os

MARK = "rhRemote356a"
DIAG = "ci_diag_batch356a_remote.txt"
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
    /** 不为空时先连这台跳板机, 再经它的 direct-tcpip 隧道连目标主机, 相当于 OpenSSH 的 ProxyJump */
    val jumpHost: SshJumpHostConfig? = null,
) {
    val address: String
        get() = "$username@$host:$port"

    // 不让凭据出现在日志和异常信息里
    override fun toString(): String =
        "SshConnectionConfig(address=$address, authType=$authType, remoteDir=$remoteDir, " +
            "hostKey=${hostKey?.fingerprint}, jumpHost=$jumpHost)"
}

/**
 * 跳板机。它只负责转发 TCP, 目标主机的认证和主机密钥校验照常进行;
 * 跳板机自己的主机密钥单独确认, 同样在认证之前校验。
 */
data class SshJumpHostConfig(
    val host: String,
    val port: Int = 22,
    val username: String,
    val authType: SshAuthType,
    val password: String? = null,
    /** OpenSSH / PEM 格式的私钥文本 */
    val privateKey: String? = null,
    val passphrase: String? = null,
    /** 为 null 时连接会抛出 [SshUnknownHostKeyException] (jumpHost = true) */
    val hostKey: SshHostKey? = null,
) {
    val address: String
        get() = "$username@$host:$port"

    override fun toString(): String =
        "SshJumpHostConfig(address=$address, authType=$authType, hostKey=${hostKey?.fingerprint})"
}

/** 测试连接的结果 */
data class SshProbeResult(
    val hostKey: SshHostKey,
    val homeDir: String,
    val shell: String,
    val remoteDirExists: Boolean,
)

/** 服务器的主机密钥尚未被信任, 需要用户确认 [hostKey] 的指纹; [jumpHost] 表示是跳板机的密钥 */
class SshUnknownHostKeyException(val hostKey: SshHostKey, val jumpHost: Boolean = false) :
    IOException("Unknown SSH ${jumpHost.hostLabel} key ${hostKey.type} ${hostKey.fingerprint}")

/** 服务器的主机密钥与已信任的不一致, 可能遭遇中间人攻击, 也可能是服务器重装过 */
class SshHostKeyChangedException(val expected: SshHostKey, val actual: SshHostKey, val jumpHost: Boolean = false) :
    IOException(
        "SSH ${jumpHost.hostLabel} key changed: expected ${expected.fingerprint}, got ${actual.type} ${actual.fingerprint}"
    )

private val Boolean.hostLabel: String
    get() = if (this) "jump host" else "host"
'''

SETTINGS = r'''package me.rerere.rikkahub.data.model

import kotlinx.serialization.Serializable
import me.rerere.workspace.ssh.SshAuthType
import me.rerere.workspace.ssh.SshHostKey

/**
 * SSH 工作区的持久化配置, 以 JSON 存在 workspaces.ssh_config 列。
 *
 * 数据库会随备份导出, 凭据字段只存 [me.rerere.rikkahub.utils.SecretCipher] 加密后的密文;
 * 密钥在 Android Keystore 中且不可导出, 换设备恢复备份后需要重新填写凭据。
 */
@Serializable
data class SshWorkspaceSettings(
    val host: String,
    val port: Int = 22,
    val username: String,
    val authType: SshAuthType = SshAuthType.PASSWORD,
    /** 远程工作目录, 绝对路径 */
    val remoteDir: String,
    /** 用户确认过的主机公钥 */
    val hostKey: SshHostKey? = null,
    val encryptedPassword: String? = null,
    val encryptedPrivateKey: String? = null,
    val encryptedPassphrase: String? = null,
    /** 经跳板机连接; 为 null 表示直连, 旧数据没有这个字段 */
    val jumpHost: SshJumpHostSettings? = null,
)

/** 跳板机的持久化配置, 凭据同样只存密文 */
@Serializable
data class SshJumpHostSettings(
    val host: String,
    val port: Int = 22,
    val username: String,
    val authType: SshAuthType = SshAuthType.PASSWORD,
    /** 用户确认过的跳板机主机公钥, 和目标主机的分开保存 */
    val hostKey: SshHostKey? = null,
    val encryptedPassword: String? = null,
    val encryptedPrivateKey: String? = null,
    val encryptedPassphrase: String? = null,
)

/** SSH 工作区编辑表单。凭据为明文; 编辑已有工作区时留空表示沿用已保存的值 */
data class SshWorkspaceDraft(
    val name: String,
    val host: String,
    val port: Int = 22,
    val username: String,
    val authType: SshAuthType = SshAuthType.PASSWORD,
    val password: String = "",
    val privateKey: String = "",
    val passphrase: String = "",
    val remoteDir: String,
    val hostKey: SshHostKey? = null,
    val jumpHost: SshJumpHostDraft? = null,
)

/** 跳板机编辑表单, 凭据规则同 [SshWorkspaceDraft] */
data class SshJumpHostDraft(
    val host: String,
    val port: Int = 22,
    val username: String,
    val authType: SshAuthType = SshAuthType.PASSWORD,
    val password: String = "",
    val privateKey: String = "",
    val passphrase: String = "",
    val hostKey: SshHostKey? = null,
)
'''

# Repository: toConnectionConfig 解密 jumpHost; toSettings 处理 jumpHost 凭据
REPO_CONN_ANCHOR = """    private fun SshWorkspaceSettings.toConnectionConfig() = SshConnectionConfig(
        host = host,
        port = port,
        username = username,
        authType = authType,
        password = encryptedPassword?.let(::decryptSecret),
        privateKey = encryptedPrivateKey?.let(::decryptSecret),
        passphrase = encryptedPassphrase?.let(::decryptSecret),
        remoteDir = remoteDir,
        hostKey = hostKey,
    )"""
REPO_CONN_NEW = """    private fun SshWorkspaceSettings.toConnectionConfig() = SshConnectionConfig(
        host = host,
        port = port,
        username = username,
        authType = authType,
        password = encryptedPassword?.let(::decryptSecret),
        privateKey = encryptedPrivateKey?.let(::decryptSecret),
        passphrase = encryptedPassphrase?.let(::decryptSecret),
        remoteDir = remoteDir,
        hostKey = hostKey,
        jumpHost = jumpHost?.let { jump ->
            SshJumpHostConfig(
                host = jump.host,
                port = jump.port,
                username = jump.username,
                authType = jump.authType,
                password = jump.encryptedPassword?.let(::decryptSecret),
                privateKey = jump.encryptedPrivateKey?.let(::decryptSecret),
                passphrase = jump.encryptedPassphrase?.let(::decryptSecret),
                hostKey = jump.hostKey,
            )
        },
    )"""

REPO_TOSETTINGS_ANCHOR = """        return SshWorkspaceSettings(
            host = host.trim(),
            port = port,
            username = username.trim(),
            authType = authType,
            remoteDir = remoteDir,
            hostKey = hostKey,
            encryptedPassword = credentials.password,
            encryptedPrivateKey = credentials.privateKey,
            encryptedPassphrase = credentials.passphrase,
        )
    }"""
REPO_TOSETTINGS_NEW = """        return SshWorkspaceSettings(
            host = host.trim(),
            port = port,
            username = username.trim(),
            authType = authType,
            remoteDir = remoteDir,
            hostKey = hostKey,
            encryptedPassword = credentials.password,
            encryptedPrivateKey = credentials.privateKey,
            encryptedPassphrase = credentials.passphrase,
            jumpHost = jumpHost?.toSettings(previous?.jumpHost),
        )
    }

    private fun SshJumpHostDraft.toSettings(previous: SshJumpHostSettings?): SshJumpHostSettings {
        require(host.isNotBlank()) { "Jump host is required" }
        require(username.isNotBlank()) { "Jump host username is required" }
        require(port in 1..65535) { "Invalid jump host port: $port" }
        val credentials = encryptCredentials(
            authType = authType,
            password = password,
            privateKey = privateKey,
            passphrase = passphrase,
            previous = previous?.let {
                EncryptedCredentials(it.encryptedPassword, it.encryptedPrivateKey, it.encryptedPassphrase)
            },
        )
        return SshJumpHostSettings(
            host = host.trim(),
            port = port,
            username = username.trim(),
            authType = authType,
            hostKey = hostKey,
            encryptedPassword = credentials.password,
            encryptedPrivateKey = credentials.privateKey,
            encryptedPassphrase = credentials.passphrase,
        )
    }"""

REPO_IMPORT_ANCHOR = "import me.rerere.workspace.ssh.SshConnectionPool\n"
REPO_IMPORT_NEW = REPO_IMPORT_ANCHOR + "import me.rerere.workspace.ssh.SshJumpHostConfig\n"


def main():
    diag = []
    ok = True

    for path, content, label in (
        ("workspace/src/main/java/me/rerere/workspace/ssh/SshConfig.kt", SSH_CONFIG, "SshConfig"),
        ("app/src/main/java/me/rerere/rikkahub/data/model/SshWorkspaceSettings.kt", SETTINGS, "Settings"),
    ):
        write(path, content)
        diag.append(label + ":wrote")
        if content.count("(") != content.count(")"):
            diag.append(label + ":UNBALANCED")
            ok = False

    repo_path = "app/src/main/java/me/rerere/rikkahub/data/repository/WorkspaceRepository.kt"
    repo = read(repo_path)
    for label, needle, repl in (
        ("repo-import", REPO_IMPORT_ANCHOR, REPO_IMPORT_NEW),
        ("repo-conn", REPO_CONN_ANCHOR, REPO_CONN_NEW),
        ("repo-tosettings", REPO_TOSETTINGS_ANCHOR, REPO_TOSETTINGS_NEW),
    ):
        if repl in repo:
            diag.append(label + ":already")
            continue
        if repo.count(needle) != 1:
            diag.append(label + ":ANCHOR-MISMATCH(" + str(repo.count(needle)) + ")")
            ok = False
            continue
        repo = repo.replace(needle, repl, 1)
        diag.append(label + ":ok")
    write(repo_path, repo)

    for needle in ("jumpHost = jumpHost?.let { jump ->", "private fun SshJumpHostDraft.toSettings("):
        if needle not in repo:
            diag.append("repo:MISSING:" + needle[:30])
            ok = False
    for needle in ("class SshJumpHostConfig(", "jumpHost: SshJumpHostConfig? = null,", "val jumpHost: Boolean = false"):
        if needle not in SSH_CONFIG:
            diag.append("config:MISSING:" + needle[:30])
            ok = False

    diag.append("RESULT:" + ("OK" if ok else "FAIL"))
    with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
        f.write("\n".join(diag) + "\n")
    log(" | ".join(diag))
    if not ok:
        print("::error title=batch356a::" + " | ".join(diag))


main()
