-- chatbotdb: 로그인 세션 및 세션 이력 테이블
-- user_info 테이블이 이미 존재한다고 가정합니다.

USE chatbotdb;

CREATE TABLE IF NOT EXISTS `cb_request_queue` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '요청 ID',
  `db_user_id` bigint unsigned DEFAULT NULL COMMENT 'user_info.id (로그인 실패 시 NULL)',
  `session_id` bigint unsigned DEFAULT NULL COMMENT 'user_session.id',
  `status` varchar(20) NOT NULL COMMENT '요청 상태 (pending, in_progress, completed, failed, cancelled, incomplete)',
  `request_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '요청 메시지',
  `error_message` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '에러 메시지',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '요청 시각',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='요청 대기 큐';
