-- chatbotdb: 로그인 세션 및 세션 이력 테이블
-- user_info 테이블이 이미 존재한다고 가정합니다.

USE chatbotdb;

CREATE TABLE IF NOT EXISTS `user_session` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '세션 레코드 ID',
  `db_user_id` bigint unsigned NOT NULL COMMENT 'user_info.id',
  `session_token` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '세션 토큰',
  `status` enum('active','logged_out','expired') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active' COMMENT '세션 상태',
  `ip_address` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '로그인 IP',
  `user_agent` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '브라우저/클라이언트 정보',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '세션 생성 시각',
  `last_activity_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '마지막 활동 시각',
  `expires_at` datetime DEFAULT NULL COMMENT '만료 시각',
  `logged_out_at` datetime DEFAULT NULL COMMENT '로그아웃 시각',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_session_token` (`session_token`),
  KEY `idx_session_user_status` (`db_user_id`, `status`),
  KEY `idx_session_expires` (`expires_at`),
  CONSTRAINT `fk_user_session_user` FOREIGN KEY (`db_user_id`) REFERENCES `user_info` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='활성 로그인 세션';

CREATE TABLE IF NOT EXISTS `user_session_log` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '이력 ID',
  `db_user_id` bigint unsigned DEFAULT NULL COMMENT 'user_info.id (로그인 실패 시 NULL)',
  `session_id` bigint unsigned DEFAULT NULL COMMENT 'user_session.id',
  `event_type` enum(
    'login_success',
    'login_failed',
    'logout',
    'session_expired',
    'password_reset'
  ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '이벤트 유형',
  `login_id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '시도한 로그인 ID (user_info.login_id)',
  `ip_address` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_agent` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `message` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '부가 설명',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '이벤트 시각',
  PRIMARY KEY (`id`),
  KEY `idx_session_log_user` (`db_user_id`),
  KEY `idx_session_log_session` (`session_id`),
  KEY `idx_session_log_event_created` (`event_type`, `created_at`),
  CONSTRAINT `fk_session_log_user` FOREIGN KEY (`db_user_id`) REFERENCES `user_info` (`id`),
  CONSTRAINT `fk_session_log_session` FOREIGN KEY (`session_id`) REFERENCES `user_session` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='로그인·세션 이력';

