package com.agriroots.app;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(android.os.Bundle savedInstanceState) {
        registerPlugin(AgriRootsPermissionsPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
