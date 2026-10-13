package com.farmly.app;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(android.os.Bundle savedInstanceState) {
        registerPlugin(FarmlyPermissionsPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
