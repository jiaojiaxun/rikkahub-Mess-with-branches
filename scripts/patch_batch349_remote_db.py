#!/usr/bin/env python3
# rhRemote349: SSH 工作区数据层
#   - SecretCipher: Android Keystore AES/GCM，凭据只存密文
#   - SshWorkspaceSettings / SshWorkspaceDraft
#   - WorkspaceEntity 增加 type / ssh_config 与能力查询
#   - AppDatabase v37 -> v38 手写迁移 + DI 注册
# 锚点按 CI 真形态 (snapshot) 写: DataSourceModule 已注册到 Migration_36_37。
import os

MARK = "rhRemote349"
DIAG = "ci_diag_batch349_remote.txt"
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


CIPHER = r'''package me.rerere.rikkahub.utils

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyStore
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * 用 Android Keystore 中不可导出的 AES 密钥加解密少量敏感字符串 (如 SSH 密码、私钥)。
 *
 * 密文和密钥绑定在本机: 卸载重装或换设备恢复备份后无法解密, 调用方需提示用户重新填写。
 */
object SecretCipher {
    private const val KEYSTORE = "AndroidKeyStore"
    private const val KEY_ALIAS = "rikkahub_secret_cipher"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"
    private const val VERSION_PREFIX = "v1:"
    private const val IV_SIZE = 12
    private const val TAG_BITS = 128

    fun encrypt(plaintext: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, secretKey())
        val ciphertext = cipher.doFinal(plaintext.toByteArray(Charsets.UTF_8))
        return VERSION_PREFIX + Base64.getEncoder().encodeToString(cipher.iv + ciphertext)
    }

    fun decrypt(value: String): String {
        require(value.startsWith(VERSION_PREFIX)) { "Unsupported secret format" }
        val bytes = Base64.getDecoder().decode(value.removePrefix(VERSION_PREFIX))
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, secretKey(), GCMParameterSpec(TAG_BITS, bytes, 0, IV_SIZE))
        return cipher.doFinal(bytes, IV_SIZE, bytes.size - IV_SIZE).toString(Charsets.UTF_8)
    }

    @Synchronized
    private fun secretKey(): SecretKey {
        val keyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE).apply {
            init(
                KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build()
            )
        }.generateKey()
    }
}
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
)
'''

ENTITY_FIELDS = r'''    @ColumnInfo("type", defaultValue = "LOCAL")
    val type: String = WorkspaceType.LOCAL.name,
    // SSH 工作区的连接配置 (SshWorkspaceSettings 的 JSON, 凭据为 Keystore 密文), 本地工作区为 null
    @ColumnInfo("ssh_config")
    val sshConfig: String? = null,
'''

ENTITY_METHODS = r'''    fun isSsh(): Boolean = type == WorkspaceType.SSH.name

    fun capabilities(): WorkspaceCapabilities =
        runCatching { WorkspaceType.valueOf(type) }.getOrDefault(WorkspaceType.LOCAL).capabilities

    fun sshSettings(): SshWorkspaceSettings? = sshConfig?.let { config ->
        runCatching { JsonInstant.decodeFromString<SshWorkspaceSettings>(config) }.getOrNull()
    }

    /** 工作区文件目录在执行环境内的绝对路径, 不需要连接即可得到, 供界面展示 */
    fun workspaceDir(): String =
        if (isSsh()) {
            sshSettings()?.let { SshWorkspaceBackend.layoutOf(it.remoteDir).workspaceDir } ?: "/"
        } else {
            WorkspaceManager.ROOTFS_WORKSPACE_DIR
        }

    /** 是否有可用的交互式终端入口 */
    fun supportsTerminal(): Boolean =
        capabilities().terminal && shellStatus != WorkspaceShellStatus.DISABLED.name

'''

MIGRATION = r'''// rhRemote349: v38 adds type / ssh_config to workspaces. Both carry defaults, so
// existing local workspaces keep working without a data rewrite.
class Migration_37_38 : Migration(37, 38) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("ALTER TABLE workspaces ADD COLUMN type TEXT NOT NULL DEFAULT 'LOCAL'")
        db.execSQL("ALTER TABLE workspaces ADD COLUMN ssh_config TEXT")
    }
}

'''


def main():
    diag = []
    ok = True

    cipher_path = "app/src/main/java/me/rerere/rikkahub/utils/SecretCipher.kt"
    settings_path = "app/src/main/java/me/rerere/rikkahub/data/model/SshWorkspaceSettings.kt"
    for path, content, label in (
        (cipher_path, CIPHER, "SecretCipher"),
        (settings_path, SETTINGS, "SshWorkspaceSettings"),
    ):
        if os.path.exists(path):
            diag.append(label + ":exists")
        else:
            write(path, content)
            diag.append(label + ":wrote")

    # WorkspaceEntity
    entity_path = "app/src/main/java/me/rerere/rikkahub/data/db/entity/WorkspaceEntity.kt"
    entity = read(entity_path)
    if 'ColumnInfo("type"' in entity:
        diag.append("entity:already")
    else:
        # imports
        if "me.rerere.rikkahub.data.model.SshWorkspaceSettings" not in entity:
            entity = entity.replace(
                "import me.rerere.rikkahub.utils.JsonInstant\n",
                "import me.rerere.rikkahub.data.model.SshWorkspaceSettings\n"
                "import me.rerere.rikkahub.utils.JsonInstant\n"
                "import me.rerere.workspace.WorkspaceCapabilities\n"
                "import me.rerere.workspace.WorkspaceManager\n"
                "import me.rerere.workspace.WorkspaceType\n"
                "import me.rerere.workspace.ssh.SshWorkspaceBackend\n",
                1,
            )
            diag.append("entity:imports")
        anchor_field = '    @ColumnInfo("shell_compatibility_mode", defaultValue = "0")\n    val shellCompatibilityMode: Boolean = false,\n'
        if entity.count(anchor_field) != 1:
            diag.append("entity:field-anchor(" + str(entity.count(anchor_field)) + ")")
            ok = False
        else:
            entity = entity.replace(anchor_field, anchor_field + ENTITY_FIELDS, 1)
            diag.append("entity:fields")
        anchor_method = "    fun toolApprovalOverrides(): Map<String, Boolean> = runCatching {"
        if entity.count(anchor_method) != 1:
            diag.append("entity:method-anchor(" + str(entity.count(anchor_method)) + ")")
            ok = False
        else:
            entity = entity.replace(anchor_method, ENTITY_METHODS + anchor_method, 1)
            diag.append("entity:methods")
        write(entity_path, entity)

    # AppDatabase: version + migration class
    db_path = "app/src/main/java/me/rerere/rikkahub/data/db/AppDatabase.kt"
    db = read(db_path)
    if "class Migration_37_38" in db:
        diag.append("dbclass:already")
    else:
        if db.count("    version = 37,") != 1:
            diag.append("dbclass:version-anchor(" + str(db.count("    version = 37,")) + ")")
            ok = False
        else:
            db = db.replace("    version = 37,", "    version = 38,", 1)
            diag.append("dbclass:version38")
        anchor_obj = "object TokenUsageConverter {"
        if db.count(anchor_obj) != 1:
            diag.append("dbclass:insert-anchor(" + str(db.count(anchor_obj)) + ")")
            ok = False
        else:
            db = db.replace(anchor_obj, MIGRATION + anchor_obj, 1)
            diag.append("dbclass:migration")
        write(db_path, db)

    # DI: import + addMigrations
    di_path = "app/src/main/java/me/rerere/rikkahub/di/DataSourceModule.kt"
    di = read(di_path)
    if "Migration_37_38" in di:
        diag.append("di:already")
    else:
        imp_anchor = "import me.rerere.rikkahub.data.db.Migration_36_37 // rhShortMem"
        if di.count(imp_anchor) != 1:
            diag.append("di:import-anchor(" + str(di.count(imp_anchor)) + ")")
            ok = False
        else:
            di = di.replace(
                imp_anchor,
                imp_anchor + "\nimport me.rerere.rikkahub.data.db.Migration_37_38 // rhRemote349",
                1,
            )
            diag.append("di:import")
        reg_anchor = "Migration_35_36(), Migration_36_37())"
        if di.count(reg_anchor) != 1:
            diag.append("di:reg-anchor(" + str(di.count(reg_anchor)) + ")")
            ok = False
        else:
            di = di.replace(reg_anchor, "Migration_35_36(), Migration_36_37(), Migration_37_38())", 1)
            diag.append("di:register")
        write(di_path, di)

    # 自检
    for label, block in (("cipher", CIPHER), ("settings", SETTINGS), ("entity_fields", ENTITY_FIELDS),
                         ("entity_methods", ENTITY_METHODS), ("migration", MIGRATION)):
        if block.count("(") != block.count(")"):
            diag.append(label + ":UNBALANCED(" + str(block.count("(")) + "/" + str(block.count(")")) + ")")
            ok = False
    final_entity = read(entity_path)
    for needle in (
        "fun isSsh(): Boolean",
        "fun capabilities(): WorkspaceCapabilities",
        "fun sshSettings(): SshWorkspaceSettings?",
        "fun workspaceDir(): String",
        'ColumnInfo("ssh_config")',
    ):
        if needle not in final_entity:
            diag.append("entity:MISSING:" + needle[:28])
            ok = False
    final_db = read(db_path)
    if "version = 38" not in final_db or "ALTER TABLE workspaces ADD COLUMN type" not in final_db:
        diag.append("db:MISS")
        ok = False
    final_di = read(di_path)
    if "Migration_37_38()" not in final_di:
        diag.append("di:MISS")
        ok = False

    diag.append("RESULT:" + ("OK" if ok else "FAIL"))
    with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
        f.write("\n".join(diag) + "\n")
    log(" | ".join(diag))
    if not ok:
        print("::error title=batch349::" + " | ".join(diag))


main()
