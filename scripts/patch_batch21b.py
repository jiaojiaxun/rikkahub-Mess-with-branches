from pathlib import Path

ROOT = Path.cwd()
PATH = "app/proguard-rules.pro"

text = (ROOT / PATH).read_text(encoding="utf-8")

if "-keep class com.whl.quickjs" in text:
    print("batch21b: proguard keep rules already present")
else:
    ADD = """
# --- rh-batch21b: R8 keep rules (minify stays on, obfuscation stays off) ---
# QuickJS JNI: native code looks up Java callbacks (Console impl, module loaders)
# by exact name; shrinking/optimizing them away breaks eval_javascript at runtime.
-keep class com.whl.quickjs.** { *; }
-keep class * implements com.whl.quickjs.QuickJSContext$Console { *; }

# Pebble templates resolve members reflectively at render time.
-keep class io.pebbletemplates.** { *; }

# kotlinx.serialization: generated serializers are looked up reflectively; enum
# values are serialized by name via valueOf().
-keepattributes RuntimeVisibleAnnotations,AnnotationDefault
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

# Datastore Settings schema: polymorphic type discriminators are written by
# class-name; renaming/relocating a settings class breaks loading old backups.
-keep class me.rerere.rikkahub.data.datastore.** { *; }
-keep class me.rerere.rikkahub.data.model.** { *; }

# AI module message/part models cross the :ai/:app serialization boundary.
-keep class me.rerere.ai.ui.** { *; }
-keep class me.rerere.ai.core.** { *; }
"""
    (ROOT / PATH).write_text(text.rstrip() + "\n" + ADD, encoding="utf-8")
    print("batch21b: R8 keep rules appended (QuickJS JNI, Pebble, kotlinx.serialization, enums, settings/data models)")
