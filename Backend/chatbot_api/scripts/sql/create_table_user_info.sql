-- chatbotdb: 로그인 세션 및 세션 이력 테이블
-- user_info 테이블이 이미 존재한다고 가정합니다.

USE chatbotdb;

CREATE TABLE IF NOT EXISTS `user_info` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '사용자 고유 ID',
  `login_id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '로그인 ID',
  `email` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '이메일',
  `password_hash` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '비밀번호 해시 (bcrypt/argon2 권장)',
  `username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '사용자명/닉네임',
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '실명',
  `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '전화번호',
  `profile_image` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '프로필 이미지 URL',
  `role` enum('user','admin','moderator','channel') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'user' COMMENT '권한 등급',
  `status` enum('active','inactive','suspended','deleted') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active' COMMENT '계정 상태',
  `email_verified` tinyint(1) NOT NULL DEFAULT '0' COMMENT '이메일 인증 여부',
  `last_login_at` datetime DEFAULT NULL COMMENT '마지막 로그인 시각',
  `last_login_ip` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '마지막 로그인 IP (IPv6 호환)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '가입 일시',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '정보 수정\r\n  일시',
  `deleted_at` datetime DEFAULT NULL COMMENT '탈퇴 일시 (소프트 삭제)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_email` (`email`),
  UNIQUE KEY `uk_user_id` (`login_id`),
  KEY `idx_users_status` (`status`),
  KEY `idx_users_created_at` (`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='웹사이트 사용자 정보';
