# ProGuard/R8 rules for Ueberzeit-Rechner Android app.

# Keep Room entities and DAOs
-keep class de.bluelight.ueberzeitrechner.data.** { *; }
-keepclassmembers class de.bluelight.ueberzeitrechner.data.** { *; }

# Room generic signatures and TypeConverter
-keepattributes Signature, InnerClasses, EnclosingMethod
-keepclassmembers class * {
    @androidx.room.* <methods>;
}
-keep class androidx.room.** { *; }

# Compose runtime and compiler metadata
-keep class androidx.compose.runtime.** { *; }
-keepclassmembers class androidx.compose.runtime.** { *; }

# Keep Kotlin metadata and nullability annotations for Compose/Room
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations
-keepclassmembers class * {
    @kotlin.Metadata *;
}

# Keep Material3/Navigation Compose public APIs used in reflection
-keep class androidx.compose.material3.** { public *; }
-keep class androidx.navigation.compose.** { public *; }

# Suppress warnings for libraries we know are safe
-dontwarn java.lang.invoke.StringConcatFactory
-dontwarn javax.lang.model.element.Modifier
-dontwarn org.bouncycastle.jsse.BCSSLParameters
-dontwarn org.bouncycastle.jsse.provider.BouncyCastleJsseProvider
-dontwarn org.conscrypt.Conscrypt$Version
-dontwarn org.conscrypt.Conscrypt
-dontwarn org.conscrypt.ConscryptHostnameVerifier
-dontwarn org.openjsse.javax.net.ssl.SSLParameters
-dontwarn org.openjsse.javax.net.ssl.SSLSocket
-dontwarn org.openjsse.net.ssl.OpenJSSE
