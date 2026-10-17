# Keep R8 shrinking and optimization enabled, but preserve class/member names for
# stable diagnostics and settings/serialization compatibility.
-dontobfuscate

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
