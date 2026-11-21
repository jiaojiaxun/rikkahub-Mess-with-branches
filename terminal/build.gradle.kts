plugins {
    id("rikkahub.android.library")
}

android {
    namespace = "me.rerere.terminal"

    defaultConfig {
        ndk {
            abiFilters += listOf("arm64-v8a")
        }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }
}

// rhLocalTerminal357: libtermux.so powers the local workspace terminal


dependencies {
    testImplementation(libs.junit)
}
