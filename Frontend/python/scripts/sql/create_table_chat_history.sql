-- chatbotdb: 로그인 세션 및 세션 이력 테이블
-- user_info 테이블이 이미 존재한다고 가정합니다.

USE chatbotdb;

CREATE TABLE IF NOT EXISTS `cb_chat_history` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '이력 ID',
  `db_user_id` bigint unsigned DEFAULT NULL COMMENT 'user_info.id (로그인 실패 시 NULL)',
  `session_id` bigint unsigned DEFAULT NULL COMMENT 'user_session.id',
  `role` enum('user','assistant') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '역할',
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '내용',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '이벤트 시각',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='채팅 이력';
