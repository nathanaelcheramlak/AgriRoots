import { Capacitor, registerPlugin } from "@capacitor/core";
import { Geolocation } from "@capacitor/geolocation";

const FarmlyPermissions = registerPlugin("FarmlyPermissions");

export function isNativeApp() {
  return Capacitor.isNativePlatform?.() || Capacitor.getPlatform?.() !== "web";
}

export async function requestMicrophonePermission() {
  if (!isNativeApp()) {
    return "granted";
  }

  const result = await FarmlyPermissions.requestMicrophone();
  if (result?.microphone !== "granted") {
    const error = new Error("Microphone permission denied.");
    error.name = "NotAllowedError";
    throw error;
  }

  return result.microphone;
}

export async function getCurrentFarmlyPosition(options) {
  if (!isNativeApp()) {
    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, options);
    });
  }

  let permissions;
  try {
    permissions = await Geolocation.checkPermissions();
  } catch {
    permissions = null;
  }

  if (permissions?.location !== "granted" && permissions?.coarseLocation !== "granted") {
    permissions = await Geolocation.requestPermissions({ permissions: ["location"] });
  }

  if (permissions?.location !== "granted" && permissions?.coarseLocation !== "granted") {
    const error = new Error("Location permission denied.");
    error.code = 1;
    throw error;
  }

  return Geolocation.getCurrentPosition(options);
}
