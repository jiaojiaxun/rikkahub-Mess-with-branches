from pathlib import Path

ROOT = Path.cwd()
PATH = "app/proguard-rules.pro"

text = (ROOT / PATH).read_text(encoding="utf-8")

if "rh-batch21b" in text:
    print("batch21b v3: already applied")
    raise SystemExit(0)

# v3 教训（#84/#85 annotations 实证）：v1/v2 的
#   -keep class io.pebbletemplates.** { *; }
# 把 Pebble 整库（含 CaffeineTagCache）拉进 R8 root set，而 caffeine 不在
# release classpath → "Missing class com.github.benmanes.caffeine.cache.Cache"
# 硬失败。#78（无 21b）R8 通过证明 Pebble 无需 keep（相关类本来就会被剪掉）。
# v3 原则：只保留 JNI/反射/序列化确需的最小规则，禁止整库通配 keep——
# 那既让压缩失效（用户要求只压缩不混淆），又把不可达的缺失引用变成硬错误。
ADD = """
# --- rh-batch21b v3: minimal R8 keep rules (minify on, obfuscation off via -dontobfuscate) ---
# QuickJS JNI: native code resolves Java callbacks by exact name.
-keep class com.whl.quickjs.** { *; }

# kotlinx.serialization: generated serializers + enum valueOf are reflective.
-keepattributes *Annotation*, Signature, InnerClasses, EnclosingMethod
-keepclassmembers class * extends java.lang.Enum {
    public static **[] values();
    public static ** valueOf(java.lang.String);
}
-keep,includedescriptorclasses class me.rerere.rikkahub.**$$serializer { *; }
-keepclassmembers class me.rerere.rikkahub.** {
    *** Companion;
}
-keepclasseswithmembers class me.rerere.rikkahub.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Pebble's optional Caffeine cache backend is NOT on the release classpath; its
# classes are tree-shaken when unreachable. Never keep io.pebbletemplates.**
# wholesale - that made R8 resolve the missing Caffeine refs and hard-fail
# (runs #84/#85). The dontwarn below is insurance only.
-dontwarn com.github.benmanes.caffeine.**
"""

(ROOT / PATH).write_text(text.rstrip() + "\n" + ADD, encoding="utf-8")
print("batch21b v3: minimal R8 keeps (removed wholesale pebble/datastore/model/ai keeps)")
