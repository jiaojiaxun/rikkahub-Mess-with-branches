#!/usr/bin/env python3
# rhRemote355a: 终端模块骨架 + 四个基础类 (从上游 rikkahub/rikkahub terminal 模块原样搬运)
# 本批纯新增、无 native (SSH 终端不需要 termux_pty.cpp, LocalPtyTransport 留二期)。
# app 尚不依赖 :terminal, 不影响 APK; 仅为 355b-e 搬运铺路。
import os

DIAG = "ci_diag_batch355a_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, t):
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(p, "w", encoding="utf-8") as f:
        f.write(t)


BUILD = r'''plugins {
    id("rikkahub.android.library")
}

android {
    namespace = "me.rerere.terminal"
}

dependencies {
    testImplementation(libs.junit)
}
'''

MANIFEST = '''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" />
'''

TRANSPORT = r'''package com.termux.terminal;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * The process behind a {@link TerminalSession}, e.g. a local pty subprocess ({@link LocalPtyTransport}) or a shell on a
 * remote host.
 * <p>
 * Threading: {@link #start(int, int)} and {@link #waitFor()} are called on a background thread and may block. The
 * streams are used by dedicated reader and writer threads once started. {@link #setWindowSize(int, int)},
 * {@link #kill()} and {@link #close()} are called on the main thread and must not block.
 */
public interface TerminalTransport {

    /** Start the process with the initial window size. Called once; a thrown exception fails the session. */
    void start(int columns, int rows) throws IOException;

    /** Output of the process, read until end of stream. */
    InputStream getInputStream();

    /** Input of the process. */
    OutputStream getOutputStream();

    /** Inform the process of a new window size. Only called after a successful {@link #start(int, int)}. */
    void setWindowSize(int columns, int rows);

    /**
     * Block until the process has exited.
     *
     * @return the exit status of the process, or the negated signal that stopped it.
     */
    int waitFor();

    /** Forcefully end the process. May be called while {@link #start(int, int)} is still running. */
    void kill();

    /** Release resources after the process has exited or failed to start. */
    void close();

    /** A line printed in the terminal before starting, e.g. while connecting to a remote host, or null for none. */
    default String describeStart() {
        return null;
    }

    /** The line printed in the terminal once the process has exited with the status from {@link #waitFor()}. */
    default String describeExit(int exitStatus) {
        String description = "Process completed";
        if (exitStatus > 0) {
            // Non-zero process exit.
            description += " (code " + exitStatus + ")";
        } else if (exitStatus < 0) {
            // Negated signal.
            description += " (signal " + (-exitStatus) + ")";
        }
        return description + " - press Enter";
    }

}
'''

CLIENT = r'''package com.termux.terminal;

/**
 * The interface for communication between {@link TerminalSession} and its client. It is used to
 * send callbacks to the client when {@link TerminalSession} changes or for sending other
 * back data to the client like logs.
 */
public interface TerminalSessionClient {

    void onTextChanged(TerminalSession changedSession);

    void onTitleChanged(TerminalSession changedSession);

    void onSessionFinished(TerminalSession finishedSession);

    void onCopyTextToClipboard(TerminalSession session, String text);

    void onPasteTextFromClipboard(TerminalSession session);

    void onBell(TerminalSession session);

    void onColorsChanged(TerminalSession session);

    void onTerminalCursorStateChange(boolean state);



    Integer getTerminalCursorStyle();



    void logError(String tag, String message);

    void logWarn(String tag, String message);

    void logInfo(String tag, String message);

    void logDebug(String tag, String message);

    void logVerbose(String tag, String message);

    void logStackTraceWithMessage(String tag, String message, Exception e);

    void logStackTrace(String tag, Exception e);

}
'''

OUTPUT = r'''package com.termux.terminal;

import java.nio.charset.StandardCharsets;

/** A client which receives callbacks from events triggered by feeding input to a {@link TerminalEmulator}. */
public abstract class TerminalOutput {

    /** Write a string using the UTF-8 encoding to the terminal client. */
    public final void write(String data) {
        if (data == null) return;
        byte[] bytes = data.getBytes(StandardCharsets.UTF_8);
        write(bytes, 0, bytes.length);
    }

    /** Write bytes to the terminal client. */
    public abstract void write(byte[] data, int offset, int count);

    /** Notify the terminal client that the terminal title has changed. */
    public abstract void titleChanged(String oldTitle, String newTitle);

    /** Notify the terminal client that text should be copied to clipboard. */
    public abstract void onCopyTextToClipboard(String text);

    /** Notify the terminal client that text should be pasted from clipboard. */
    public abstract void onPasteTextFromClipboard();

    /** Notify the terminal client that a bell character (ASCII 7, bell, BEL, \a, ^G)) has been received. */
    public abstract void onBell();

    public abstract void onColorsChanged();

}
'''

QUEUE = r'''package com.termux.terminal;

/** A circular byte buffer allowing one producer and one consumer thread. */
final class ByteQueue {

    private final byte[] mBuffer;
    private int mHead;
    private int mStoredBytes;
    private boolean mOpen = true;

    public ByteQueue(int size) {
        mBuffer = new byte[size];
    }

    public synchronized void close() {
        mOpen = false;
        notify();
    }

    public synchronized int read(byte[] buffer, boolean block) {
        while (mStoredBytes == 0 && mOpen) {
            if (block) {
                try {
                    wait();
                } catch (InterruptedException e) {
                    // Ignore.
                }
            } else {
                return 0;
            }
        }
        if (!mOpen) return -1;

        int totalRead = 0;
        int bufferLength = mBuffer.length;
        boolean wasFull = bufferLength == mStoredBytes;
        int length = buffer.length;
        int offset = 0;
        while (length > 0 && mStoredBytes > 0) {
            int oneRun = Math.min(bufferLength - mHead, mStoredBytes);
            int bytesToCopy = Math.min(length, oneRun);
            System.arraycopy(mBuffer, mHead, buffer, offset, bytesToCopy);
            mHead += bytesToCopy;
            if (mHead >= bufferLength) mHead = 0;
            mStoredBytes -= bytesToCopy;
            length -= bytesToCopy;
            offset += bytesToCopy;
            totalRead += bytesToCopy;
        }
        if (wasFull) notify();
        return totalRead;
    }

    /**
     * Attempt to write the specified portion of the provided buffer to the queue.
     * <p/>
     * Returns whether the output was totally written, false if it was closed before.
     */
    public boolean write(byte[] buffer, int offset, int lengthToWrite) {
        if (lengthToWrite + offset > buffer.length) {
            throw new IllegalArgumentException("length + offset > buffer.length");
        } else if (lengthToWrite <= 0) {
            throw new IllegalArgumentException("length <= 0");
        }

        final int bufferLength = mBuffer.length;

        synchronized (this) {
            while (lengthToWrite > 0) {
                while (bufferLength == mStoredBytes && mOpen) {
                    try {
                        wait();
                    } catch (InterruptedException e) {
                        // Ignore.
                    }
                }
                if (!mOpen) return false;
                final boolean wasEmpty = mStoredBytes == 0;
                int bytesToWriteBeforeWaiting = Math.min(lengthToWrite, bufferLength - mStoredBytes);
                lengthToWrite -= bytesToWriteBeforeWaiting;

                while (bytesToWriteBeforeWaiting > 0) {
                    int tail = mHead + mStoredBytes;
                    int oneRun;
                    if (tail >= bufferLength) {
                        // Buffer: [.............]
                        // ________________H_______T
                        // =>
                        // Buffer: [.............]
                        // ___________T____H
                        // onRun= _____----_
                        tail = tail - bufferLength;
                        oneRun = mHead - tail;
                    } else {
                        oneRun = bufferLength - tail;
                    }
                    int bytesToCopy = Math.min(oneRun, bytesToWriteBeforeWaiting);
                    System.arraycopy(buffer, offset, mBuffer, tail, bytesToCopy);
                    offset += bytesToCopy;
                    bytesToWriteBeforeWaiting -= bytesToCopy;
                    mStoredBytes += bytesToCopy;
                }
                if (wasEmpty) notify();
            }
        }
        return true;
    }
}
'''

FILES = [
    ("terminal/src/main/java/com/termux/terminal/TerminalTransport.java", TRANSPORT, "TerminalTransport"),
    ("terminal/src/main/java/com/termux/terminal/TerminalSessionClient.java", CLIENT, "TerminalSessionClient"),
    ("terminal/src/main/java/com/termux/terminal/TerminalOutput.java", OUTPUT, "TerminalOutput"),
    ("terminal/src/main/java/com/termux/terminal/ByteQueue.java", QUEUE, "ByteQueue"),
]

diag = []
ok = True
for path, content, label in FILES:
    if os.path.exists(path):
        diag.append(label + ":exists")
    else:
        write(path, content)
        diag.append(label + ":wrote")
    if content.count("{") != content.count("}"):
        diag.append(label + ":BRACES")
        ok = False

if not os.path.exists("terminal/build.gradle.kts"):
    write("terminal/build.gradle.kts", BUILD)
    diag.append("gradle:wrote")
else:
    diag.append("gradle:exists")

if not os.path.exists("terminal/src/main/AndroidManifest.xml"):
    write("terminal/src/main/AndroidManifest.xml", MANIFEST)
    diag.append("manifest:wrote")
else:
    diag.append("manifest:exists")

# settings.gradle.kts 注册模块
sp = "settings.gradle.kts"
text = read(sp)
if 'include(":terminal")' in text:
    diag.append("settings:already")
else:
    anchor = 'include(":workspace")'
    if text.count(anchor) != 1:
        diag.append("settings:ANCHOR-MISMATCH")
        ok = False
    else:
        text = text.replace(anchor, anchor + '\ninclude(":terminal")', 1)
        write(sp, text)
        diag.append("settings:ok")

final = read(sp)
if 'include(":terminal")' not in final:
    diag.append("settings:MISS")
    ok = False

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355a::" + " | ".join(diag))
