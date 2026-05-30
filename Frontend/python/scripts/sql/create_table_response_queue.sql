-- chatbotdb: 로그인 세션 및 세션 이력 테이블
-- user_info 테이블이 이미 존재한다고 가정합니다.

USE chatbotdb;

CREATE TABLE IF NOT EXISTS `cb_response_queue` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '응답 ID',
  `request_id` bigint unsigned NOT NULL COMMENT 'request_queue.id',
  `session_id` bigint unsigned NOT NULL COMMENT 'user_session.id',
  `status` varchar(20) NOT NULL DEFAULT 'reponsed' COMMENT '응답 상태 (reponsed, received)',
  `response_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '응답 메시지',
  `image_url` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '이미지 URL',
  `audio_url` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '오디오 URL',
  `video_url` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '비디오 URL',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '응답 시각',
  PRIMARY KEY (`id`),
  KEY `idx_response_request` (`request_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='응답 대기 큐';
