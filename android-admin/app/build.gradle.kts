plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}
val releaseApi = providers.gradleProperty("ARAK_API_BASE_URL").orElse("https://example.invalid/api").get()
require(Regex("https://[A-Za-z0-9.-]+(?::[0-9]+)?/api").matches(releaseApi)) {
    "ARAK_API_BASE_URL must be an HTTPS origin followed by /api"
}

android {
    namespace = "com.arakala.admin"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.arakala.admin"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0-alpha"
        buildConfigField("String", "API_BASE_URL", "\"$releaseApi\"")
    }
    buildTypes {
        getByName("debug") {
            buildConfigField("String", "API_BASE_URL", "\"http://10.0.2.2:8000/api\"")
        }
        getByName("release") {
            isMinifyEnabled = false
        }
    }
    buildFeatures { compose = true; buildConfig = true }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}
dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.04.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.activity:activity-compose:1.10.1")
}
