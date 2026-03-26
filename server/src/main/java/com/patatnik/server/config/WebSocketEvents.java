package com.patatnik.server.config;

import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.messaging.SessionConnectedEvent;
import org.springframework.web.socket.messaging.SessionDisconnectEvent;

@Component
public class WebSocketEvents {

    @EventListener
    public void handleConnected(SessionConnectedEvent event) {
        System.out.println("WebSocket FULLY CONNECTED");
    }

    @EventListener
    public void handleDisconnect(SessionDisconnectEvent event) {
        System.out.println("WebSocket DISCONNECTED: " + event.getSessionId());
    }
}