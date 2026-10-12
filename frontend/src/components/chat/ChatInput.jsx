import { useEffect, useRef, useState } from "react";
import { Loader2, Mic, Send, Square, Image as ImageIcon, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { requestMicrophonePermission } from "@/lib/nativePermissions";

const MAX_RECORDING_MS = 45000;
const MAX_IMAGE_PIXELS = 25000000;
const MAX_IMAGE_MEGAPIXELS = Math.floor(MAX_IMAGE_PIXELS / 1000000);
const AUDIO_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/ogg",
];

const COPY = {
  en: {
    unsupported: "Voice recording is not supported in this browser.",
    recordingFailed: "Recording failed. Please try again.",
    permissionNeeded: "Microphone permission is needed for voice messages.",
    noAudio: "No audio was recorded.",
    attachImage: "Attach image",
    preview: "Selected image preview",
    stopRecording: "Stop recording",
    recordVoice: "Record voice message",
    placeholder: "Ask Farmly for advice...",
    sendMessage: "Send message",
    recording: "Recording...",
    processing: "Processing audio...",
    imageTypeError: "Please choose an image file.",
    imageReadFailed: "Could not read this image. Please choose another file.",
    imageTooLarge: "This image is {size}, over the {limit} diagnosis limit. Resize it or choose a smaller photo.",
  },
  am: {
    unsupported: "ይህ አሳሽ የድምጽ መቅዳትን አይደግፍም።",
    recordingFailed: "ድምጽ መቅዳት አልተሳካም። እባክዎ እንደገና ይሞክሩ።",
    permissionNeeded: "የድምጽ መልዕክት ለመላክ የማይክሮፎን ፈቃድ ያስፈልጋል።",
    noAudio: "ምንም ድምጽ አልተቀዳም።",
    attachImage: "ምስል አያይዝ",
    preview: "የተመረጠ ምስል ቅድመ እይታ",
    stopRecording: "መቅዳት አቁም",
    recordVoice: "የድምጽ መልዕክት ቅዳ",
    placeholder: "Farmlyን የግብርና ምክር ይጠይቁ...",
    sendMessage: "መልዕክት ላክ",
    recording: "በመቅዳት ላይ...",
    processing: "ድምጽ በሂደት ላይ...",
    imageTypeError: "እባክዎ የምስል ፋይል ይምረጡ።",
    imageReadFailed: "ይህን ምስል ማንበብ አልተቻለም። እባክዎ ሌላ ፋይል ይምረጡ።",
    imageTooLarge: "ይህ ምስል {size} ነው፣ ከ{limit} የምርመራ ገደብ በላይ ነው። ያሳንሱት ወይም ትንሽ ፎቶ ይምረጡ።",
  },
};

function getSupportedAudioMimeType() {
  if (typeof window === "undefined" || !window.MediaRecorder) {
    return "";
  }
  return AUDIO_MIME_TYPES.find((type) => window.MediaRecorder.isTypeSupported(type)) || "";
}

function writeString(view, offset, value) {
  for (let i = 0; i < value.length; i += 1) {
    view.setUint8(offset + i, value.charCodeAt(i));
  }
}

function audioBufferToWav(audioBuffer) {
  const channels = audioBuffer.numberOfChannels;
  const sampleRate = audioBuffer.sampleRate;
  const length = audioBuffer.length;
  const bytesPerSample = 2;
  const blockAlign = channels * bytesPerSample;
  const dataSize = length * blockAlign;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, channels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bytesPerSample * 8, true);
  writeString(view, 36, "data");
  view.setUint32(40, dataSize, true);

  let offset = 44;
  for (let i = 0; i < length; i += 1) {
    for (let channel = 0; channel < channels; channel += 1) {
      const sample = Math.max(-1, Math.min(1, audioBuffer.getChannelData(channel)[i]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += bytesPerSample;
    }
  }

  return new Blob([buffer], { type: "audio/wav" });
}

async function convertRecordedAudioToWav(blob) {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) {
    return blob;
  }
  const audioContext = new AudioContextClass();
  try {
    const arrayBuffer = await blob.arrayBuffer();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
    return audioBufferToWav(audioBuffer);
  } finally {
    audioContext.close?.();
  }
}

async function getImageDimensions(file) {
  if (typeof window !== "undefined" && "createImageBitmap" in window) {
    const bitmap = await createImageBitmap(file);
    const dimensions = { width: bitmap.width, height: bitmap.height };
    bitmap.close?.();
    return dimensions;
  }

  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = document.createElement("img");

    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve({ width: img.naturalWidth, height: img.naturalHeight });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Image dimensions could not be read."));
    };
    img.src = url;
  });
}

function formatImageTooLargeMessage(copy, width, height) {
  return copy.imageTooLarge
    .replace("{size}", `${width}x${height}`)
    .replace("{limit}", `${MAX_IMAGE_MEGAPIXELS}MP`);
}

export function ChatInput({ onSend, disabled, language = "en" }) {
  const [text, setText] = useState("");
  const [image, setImage] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [recordingState, setRecordingState] = useState("idle");
  const [recordingError, setRecordingError] = useState("");
  const [inputError, setInputError] = useState("");
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recordingTimeoutRef = useRef(null);
  const copy = COPY[language] || COPY.en;

  useEffect(() => {
    return () => {
      clearTimeout(recordingTimeoutRef.current);
      if (mediaRecorderRef.current?.state === "recording") {
        mediaRecorderRef.current.stop();
      }
      mediaRecorderRef.current?.stream?.getTracks().forEach((track) => track.stop());
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handleTextChange = (e) => {
    setText(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  };

  const handleImageChange = async (e) => {
    const file = e.target.files?.[0];
    setInputError("");

    try {
      if (file && !file.type.startsWith("image/")) {
        removeImage();
        setInputError(copy.imageTypeError);
      } else if (file) {
        const { width, height } = await getImageDimensions(file);
        if (width * height > MAX_IMAGE_PIXELS) {
          removeImage();
          setInputError(formatImageTooLargeMessage(copy, width, height));
          return;
        }

        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
        }
        setInputError("");
        setRecordingError("");
        setPreviewUrl(URL.createObjectURL(file));
        setImage(file);
      }
    } catch (err) {
      console.error("Failed to read selected image", err);
      removeImage();
      setInputError(copy.imageReadFailed);
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const removeImage = () => {
    setImage(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
  };

  const stopRecording = () => {
    clearTimeout(recordingTimeoutRef.current);
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state !== "recording") return;
    setRecordingState("processing");
    recorder.stop();
  };

  const startRecording = async () => {
    if (disabled || recordingState !== "idle") return;
    setRecordingError("");
    setInputError("");

    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setRecordingError(copy.unsupported);
      return;
    }

    try {
      await requestMicrophonePermission();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = getSupportedAudioMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);

      audioChunksRef.current = [];
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data?.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        setRecordingError(copy.recordingFailed);
        setRecordingState("idle");
        clearTimeout(recordingTimeoutRef.current);
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.onstop = async () => {
        clearTimeout(recordingTimeoutRef.current);
        stream.getTracks().forEach((track) => track.stop());
        const audioType = recorder.mimeType || mimeType || "audio/webm";
        const audioBlob = new Blob(audioChunksRef.current, { type: audioType });
        audioChunksRef.current = [];
        mediaRecorderRef.current = null;

        if (!audioBlob.size) {
          setRecordingError(copy.noAudio);
          setRecordingState("idle");
          return;
        }

        try {
          const wavBlob = await convertRecordedAudioToWav(audioBlob);
          onSend("", image, wavBlob);
          setText("");
          removeImage();
        } catch (err) {
          console.error("Failed to prepare recorded audio", err);
          setRecordingError(copy.recordingFailed);
        } finally {
          setRecordingState("idle");
        }
      };

      recorder.start();
      setRecordingState("recording");
      recordingTimeoutRef.current = window.setTimeout(stopRecording, MAX_RECORDING_MS);
    } catch (err) {
      console.error("Failed to start recording", err);
      setRecordingError(copy.permissionNeeded);
      setRecordingState("idle");
    }
  };

  const handleSubmit = (e) => {
    e?.preventDefault();
    if ((!text.trim() && !image) || disabled || recordingState !== "idle") return;
    setInputError("");
    
    onSend(text.trim(), image, null);
    setText("");
    removeImage();
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const isRecording = recordingState === "recording";
  const isProcessingAudio = recordingState === "processing";

  return (
    <div className="border-t border-border bg-card p-3 md:p-4 w-full">
      <form 
        onSubmit={handleSubmit}
        className="mx-auto flex max-w-3xl flex-col gap-2 rounded-xl border border-input bg-background p-2 focus-within:ring-1 focus-within:ring-ring shadow-sm"
      >
        {previewUrl && (
          <div className="relative mb-2 inline-block w-fit px-2 pt-2">
            <img 
              src={previewUrl} 
              alt={copy.preview} 
              className="h-20 w-20 rounded-md object-cover border border-border"
            />
            <button
              type="button"
              onClick={removeImage}
              className="absolute -right-2 -top-2 rounded-full bg-destructive p-1 text-destructive-foreground shadow-sm transition-transform hover:scale-110"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        )}

        <div className="flex items-end gap-2">
          <input 
            type="file"
            accept="image/*"
            className="hidden"
            ref={fileInputRef}
            onChange={handleImageChange}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="shrink-0 rounded-full text-muted-foreground hover:text-foreground"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || isRecording || isProcessingAudio}
            title={copy.attachImage}
            aria-label={copy.attachImage}
          >
            <ImageIcon className="h-5 w-5" />
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={`shrink-0 rounded-full ${
              isRecording
                ? "bg-destructive/10 text-destructive hover:bg-destructive/15 hover:text-destructive"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={isRecording ? stopRecording : startRecording}
            disabled={disabled || isProcessingAudio}
            title={isRecording ? copy.stopRecording : copy.recordVoice}
            aria-label={isRecording ? copy.stopRecording : copy.recordVoice}
          >
            {isProcessingAudio ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : isRecording ? (
              <Square className="h-4 w-4 fill-current" />
            ) : (
              <Mic className="h-5 w-5" />
            )}
          </Button>

          <textarea
            ref={textareaRef}
            value={text}
            onChange={handleTextChange}
            onKeyDown={handleKeyDown}
            placeholder={copy.placeholder}
            className="flex-1 resize-none bg-transparent py-2 px-1 outline-none min-h-[40px] max-h-[150px] text-sm custom-scrollbar"
            rows={1}
            disabled={disabled || isRecording || isProcessingAudio}
          />

          <Button
            type="submit"
            size="icon"
            className="shrink-0 rounded-full h-9 w-9"
            disabled={(!text.trim() && !image) || disabled || isRecording || isProcessingAudio}
            title={copy.sendMessage}
            aria-label={copy.sendMessage}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>

        {(isRecording || isProcessingAudio || recordingError || inputError) && (
          <div className="px-2 text-xs">
            {isRecording && <span className="text-destructive">{copy.recording}</span>}
            {isProcessingAudio && <span className="text-muted-foreground">{copy.processing}</span>}
            {recordingError && <span className="text-destructive">{recordingError}</span>}
            {inputError && <span className="text-destructive">{inputError}</span>}
          </div>
        )}
      </form>
    </div>
  );
}
