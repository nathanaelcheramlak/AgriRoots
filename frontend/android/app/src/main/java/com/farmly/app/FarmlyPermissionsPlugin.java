package com.farmly.app;

import android.Manifest;

import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

@CapacitorPlugin(
    name = "FarmlyPermissions",
    permissions = {
        @Permission(alias = "microphone", strings = { Manifest.permission.RECORD_AUDIO })
    }
)
public class FarmlyPermissionsPlugin extends Plugin {
    private static final String MICROPHONE = "microphone";

    @PluginMethod
    public void requestMicrophone(PluginCall call) {
        if (getPermissionState(MICROPHONE) == PermissionState.GRANTED) {
            resolveMicrophone(call);
            return;
        }

        requestPermissionForAlias(MICROPHONE, call, "microphonePermissionCallback");
    }

    @PermissionCallback
    private void microphonePermissionCallback(PluginCall call) {
        resolveMicrophone(call);
    }

    private void resolveMicrophone(PluginCall call) {
        JSObject result = new JSObject();
        result.put(MICROPHONE, getPermissionState(MICROPHONE).toString());
        call.resolve(result);
    }
}
