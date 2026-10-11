package com.example.sevaro_mobile

import android.media.AudioAttributes
import android.media.MediaPlayer
import android.media.Ringtone
import android.media.RingtoneManager
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File

// Sound for the simulated coverage call, using Android's own player and ringtone
// (no audio plugin). "play" speaks the server's offer MP3; it never makes speech.
class MainActivity : FlutterActivity() {
    private var player: MediaPlayer? = null
    private var tone: Ringtone? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "sevaro/sound").setMethodCallHandler { call, result ->
            when (call.method) {
                "ring" -> { ringtone(RingtoneManager.TYPE_RINGTONE, loop = true); result.success(null) }
                "chime" -> { ringtone(RingtoneManager.TYPE_NOTIFICATION, loop = false); result.success(null) }
                "stop" -> { stop(); result.success(null) }
                "play" -> play(call.arguments as ByteArray, result)
                else -> result.notImplemented()
            }
        }
    }

    private fun ringtone(type: Int, loop: Boolean) {
        stop()
        tone = RingtoneManager.getRingtone(this, RingtoneManager.getDefaultUri(type))?.apply {
            if (loop && Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) isLooping = true
            play()
        }
    }

    private fun play(mp3: ByteArray, result: MethodChannel.Result) {
        stop()
        val file = File(cacheDir, "offer.mp3").apply { writeBytes(mp3) }
        var replied = false
        player = MediaPlayer().apply {
            setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            setDataSource(file.path)
            setOnPreparedListener { it.start(); if (!replied) { replied = true; result.success(null) } }
            setOnErrorListener { _, what, _ ->
                if (!replied) { replied = true; result.error("play_failed", "MediaPlayer error $what", null) }
                true
            }
            prepareAsync()
        }
    }

    private fun stop() {
        tone?.stop()
        tone = null
        player?.release()
        player = null
    }

    override fun onDestroy() {
        stop()
        super.onDestroy()
    }
}
