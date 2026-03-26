package com.patatnik.server.jwt;

import com.patatnik.server.model.User;
import com.patatnik.server.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.MessageDeliveryException;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ChannelInterceptor;
import org.springframework.messaging.support.MessageHeaderAccessor;
import org.springframework.stereotype.Component;

import java.security.Principal;

@Component
@RequiredArgsConstructor
public class JwtChannelInterceptor implements ChannelInterceptor {

    private final JwtUtils jwtUtils;
    private final UserRepository userRepository;

    @Override
    public Message<?> preSend(Message<?> message, MessageChannel channel) {
        StompHeaderAccessor accessor =
                MessageHeaderAccessor.getAccessor(message, StompHeaderAccessor.class);

        if (accessor == null) return message;

        if (StompCommand.CONNECT.equals(accessor.getCommand())) {

            String authHeader = accessor.getFirstNativeHeader("Authorization");

            if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                System.out.println("Missing Authorization header");
                throw new MessageDeliveryException("Missing or invalid Authorization header");
            }

            String token = authHeader.substring(7);

            if (!jwtUtils.validate(token)) {
                throw new MessageDeliveryException("Invalid or expired JWT token");
            }

            String email = jwtUtils.getEmailFromToken(token);

            User user = userRepository.findByEmail(email)
                    .orElseThrow(() -> new MessageDeliveryException("User not found"));

            accessor.setUser(new Principal() {
                @Override
                public String getName() {
                    return user.getId().toString();
                }
            });
        }

        return message;
    }
}
