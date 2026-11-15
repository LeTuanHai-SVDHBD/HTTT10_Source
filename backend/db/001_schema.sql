-- HTTT10 | MySQL 8.4 LTS | Baseline 001 | UTC DATETIME(6)
-- Chỉ áp dụng cho CSDL mới. Không DROP, không vô hiệu hóa FOREIGN_KEY_CHECKS.
-- FK/CHECK bảo vệ cấu trúc; chống chồng lịch còn cần Service + transaction + khóa tài nguyên.
CREATE DATABASE IF NOT EXISTS httt10 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE httt10;
SET NAMES utf8mb4;
SET time_zone = '+00:00';
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- Ghi nhận phiên bản baseline SQL đã áp dụng
CREATE TABLE `schema_migrations` (
  `version` VARCHAR(32) NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`version`)
) ENGINE=InnoDB;

-- Phòng ban; ngừng nhận yêu cầu mới không xóa lịch sử
CREATE TABLE `departments` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `code` VARCHAR(32) NOT NULL,
  `name` VARCHAR(150) NOT NULL,
  `accepts_new_requests` BOOLEAN NOT NULL DEFAULT TRUE,
  `row_version` BIGINT UNSIGNED NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_departments_1` (`code`),
  CONSTRAINT `ck_dept_bool` CHECK (accepts_new_requests IN (0,1))
) ENGINE=InnoDB;

-- Tài khoản nội bộ, đồng thời là dòng khóa tài nguyên người
CREATE TABLE `users` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `employee_code` VARCHAR(32) NOT NULL,
  `full_name` VARCHAR(150) NOT NULL,
  `email` VARCHAR(254) COLLATE utf8mb4_0900_as_ci NOT NULL,
  `department_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `status` ENUM('ACTIVE','LOCKED') NOT NULL DEFAULT 'LOCKED',
  `password_hash` VARCHAR(255) NULL,
  `must_change_password` BOOLEAN NOT NULL DEFAULT TRUE,
  `auth_version` BIGINT UNSIGNED NOT NULL DEFAULT 1,
  `row_version` BIGINT UNSIGNED NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_1` (`employee_code`),
  UNIQUE KEY `uq_users_2` (`email`),
  CONSTRAINT `ck_user_flags` CHECK (must_change_password IN (0,1)),
  CONSTRAINT `ck_user_active_hash` CHECK (status <> 'ACTIVE' OR password_hash IS NOT NULL),
  CONSTRAINT `fk_users_1` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Một tài khoản kiêm nhiều nhóm quyền; không suy ra Nhân viên từ Admin
CREATE TABLE `user_roles` (
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `role` ENUM('EMPLOYEE','APPROVER','ADMIN') NOT NULL,
  `granted_by` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`user_id`, `role`),
  CONSTRAINT `fk_user_roles_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_user_roles_2` FOREIGN KEY (`granted_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Phiên JWT có thể thu hồi; không lưu chuỗi JWT
CREATE TABLE `auth_sessions` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `auth_version` BIGINT UNSIGNED NOT NULL,
  `issued_at` DATETIME(6) NOT NULL,
  `expires_at` DATETIME(6) NOT NULL,
  `revoked_at` DATETIME(6) NULL,
  PRIMARY KEY (`id`),
  KEY `ix_auth_sessions_1` (`user_id`, `revoked_at`, `expires_at`),
  CONSTRAINT `ck_session_range` CHECK (issued_at < expires_at),
  CONSTRAINT `fk_auth_sessions_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Danh mục phòng; dòng phòng tồn tại được khóa trước kiểm tra xung đột
CREATE TABLE `meeting_rooms` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `code` VARCHAR(32) NOT NULL,
  `name` VARCHAR(150) NOT NULL,
  `location` VARCHAR(255) NOT NULL,
  `accepts_new_requests` BOOLEAN NOT NULL DEFAULT TRUE,
  `row_version` BIGINT UNSIGNED NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_meeting_rooms_1` (`code`),
  CONSTRAINT `ck_room_flag` CHECK (accepts_new_requests IN (0,1))
) ENGINE=InnoDB;

-- Thiết bị hiện có để lọc phòng
CREATE TABLE `room_equipment` (
  `room_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `equipment_code` VARCHAR(40) NOT NULL,
  `display_name` VARCHAR(120) NOT NULL,
  `quantity` SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  PRIMARY KEY (`room_id`, `equipment_code`),
  CONSTRAINT `ck_equipment_qty` CHECK (quantity > 0),
  CONSTRAINT `fk_room_equipment_1` FOREIGN KEY (`room_id`) REFERENCES `meeting_rooms` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Phân công duyệt phòng có FK thật; không dùng scope_id đa nghĩa
CREATE TABLE `room_approvers` (
  `room_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
  `granted_by` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`room_id`, `user_id`),
  KEY `ix_room_approvers_1` (`user_id`, `is_active`),
  CONSTRAINT `ck_room_approver_flag` CHECK (is_active IN (0,1)),
  CONSTRAINT `fk_room_approvers_1` FOREIGN KEY (`room_id`) REFERENCES `meeting_rooms` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_room_approvers_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_room_approvers_3` FOREIGN KEY (`granted_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Phân công duyệt công tác theo phòng ban
CREATE TABLE `department_approvers` (
  `department_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
  `granted_by` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`department_id`, `user_id`),
  KEY `ix_department_approvers_1` (`user_id`, `is_active`),
  CONSTRAINT `ck_dept_approver_flag` CHECK (is_active IN (0,1)),
  CONSTRAINT `fk_department_approvers_1` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_department_approvers_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_department_approvers_3` FOREIGN KEY (`granted_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Lịch sử sức chứa, đệm và giờ phục vụ; Service chỉ thêm mốc hiệu lực hợp lệ
CREATE TABLE `room_policy_versions` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `room_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `effective_from` DATETIME(6) NOT NULL,
  `capacity` SMALLINT UNSIGNED NOT NULL,
  `buffer_minutes` SMALLINT UNSIGNED NOT NULL DEFAULT 15,
  `created_by` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_room_policy_versions_1` (`room_id`, `effective_from`),
  UNIQUE KEY `uq_room_policy_versions_2` (`room_id`, `id`),
  CONSTRAINT `ck_policy_capacity` CHECK (capacity > 0),
  CONSTRAINT `fk_room_policy_versions_1` FOREIGN KEY (`room_id`) REFERENCES `meeting_rooms` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_room_policy_versions_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Các khoảng phục vụ trong tuần của một phiên bản cấu hình
CREATE TABLE `room_weekly_windows` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `policy_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `weekday` TINYINT UNSIGNED NOT NULL,
  `start_time` TIME NOT NULL,
  `end_time` TIME NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_room_weekly_windows_1` (`policy_id`, `weekday`, `start_time`),
  CONSTRAINT `ck_weekly_day` CHECK (weekday BETWEEN 1 AND 7),
  CONSTRAINT `ck_weekly_range` CHECK (start_time >= '00:00:00' AND end_time <= '24:00:00' AND start_time < end_time),
  CONSTRAINT `fk_room_weekly_windows_1` FOREIGN KEY (`policy_id`) REFERENCES `room_policy_versions` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Ngoại lệ theo ngày: nghỉ hoặc thay toàn bộ các khoảng trong ngày
CREATE TABLE `room_calendar_days` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `policy_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `local_date` DATE NOT NULL,
  `is_closed` BOOLEAN NOT NULL,
  `reason` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_room_calendar_days_1` (`policy_id`, `local_date`),
  CONSTRAINT `ck_calendar_flag` CHECK (is_closed IN (0,1)),
  CONSTRAINT `fk_room_calendar_days_1` FOREIGN KEY (`policy_id`) REFERENCES `room_policy_versions` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Khoảng phục vụ thay thế cho ngày ngoại lệ mở cửa
CREATE TABLE `room_calendar_windows` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `calendar_day_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `start_time` TIME NOT NULL,
  `end_time` TIME NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_room_calendar_windows_1` (`calendar_day_id`, `start_time`),
  CONSTRAINT `ck_calendar_range` CHECK (start_time >= '00:00:00' AND end_time <= '24:00:00' AND start_time < end_time),
  CONSTRAINT `fk_room_calendar_windows_1` FOREIGN KEY (`calendar_day_id`) REFERENCES `room_calendar_days` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Định danh lịch; chỉ current_revision_id quyết định phiên bản hiệu lực
CREATE TABLE `schedule_roots` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `kind` ENUM('MEETING','WORK') NOT NULL,
  `created_by` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `current_revision_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `row_version` BIGINT UNSIGNED NOT NULL DEFAULT 1,
  `cancelled_at` DATETIME(6) NULL,
  `cancelled_by` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `cancel_reason` VARCHAR(1000) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_schedule_roots_1` (`id`, `kind`),
  KEY `ix_schedule_roots_1` (`created_by`, `created_at`),
  CONSTRAINT `ck_root_cancel` CHECK ((cancelled_at IS NULL AND cancelled_by IS NULL AND cancel_reason IS NULL) OR (cancelled_at IS NOT NULL AND cancelled_by IS NOT NULL AND cancel_reason IS NOT NULL AND CHAR_LENGTH(TRIM(cancel_reason)) > 0 AND current_revision_id IS NOT NULL)),
  CONSTRAINT `fk_schedule_roots_1` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_schedule_roots_2` FOREIGN KEY (`cancelled_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Nội dung bất biến; ánh xạ kế thừa ScheduleRevision bằng single-table inheritance
CREATE TABLE `schedule_revisions` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `schedule_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `kind` ENUM('MEETING','WORK') NOT NULL,
  `revision_no` INT UNSIGNED NOT NULL,
  `title` VARCHAR(255) NOT NULL,
  `description` TEXT NOT NULL,
  `starts_at` DATETIME(6) NOT NULL,
  `ends_at` DATETIME(6) NOT NULL,
  `room_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `chair_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `department_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `work_location` VARCHAR(500) NULL,
  `work_context` ENUM('INTERNAL','EXTERNAL') NULL,
  `created_by` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_schedule_revisions_1` (`schedule_id`, `revision_no`),
  UNIQUE KEY `uq_schedule_revisions_2` (`schedule_id`, `id`),
  KEY `ix_schedule_revisions_1` (`room_id`, `starts_at`),
  KEY `ix_schedule_revisions_2` (`department_id`, `starts_at`),
  CONSTRAINT `ck_revision_no_positive` CHECK (revision_no > 0),
  CONSTRAINT `ck_revision_time` CHECK (starts_at < ends_at),
  CONSTRAINT `ck_revision_shape` CHECK ((kind='MEETING' AND room_id IS NOT NULL AND chair_user_id IS NOT NULL AND department_id IS NULL AND work_location IS NULL AND work_context IS NULL) OR (kind='WORK' AND room_id IS NULL AND chair_user_id IS NULL AND department_id IS NOT NULL AND work_location IS NOT NULL AND work_context IS NOT NULL)),
  CONSTRAINT `fk_schedule_revisions_1` FOREIGN KEY (`schedule_id`, `kind`) REFERENCES `schedule_roots` (`id`, `kind`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_schedule_revisions_2` FOREIGN KEY (`room_id`) REFERENCES `meeting_rooms` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_schedule_revisions_3` FOREIGN KEY (`chair_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_schedule_revisions_4` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_schedule_revisions_5` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Một người chỉ xuất hiện một lần trong mỗi bản lịch
CREATE TABLE `revision_participants` (
  `revision_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `is_required` BOOLEAN NOT NULL,
  PRIMARY KEY (`revision_id`, `user_id`),
  KEY `ix_revision_participants_1` (`user_id`, `revision_id`),
  CONSTRAINT `ck_participant_flag` CHECK (is_required IN (0,1)),
  CONSTRAINT `fk_revision_participants_1` FOREIGN KEY (`revision_id`) REFERENCES `schedule_revisions` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_revision_participants_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Yêu cầu CREATE/CHANGE/CANCEL; pending_slot UNIQUE chặn hai đề nghị chờ
CREATE TABLE `approval_proposals` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `schedule_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `kind` ENUM('CREATE','CHANGE','CANCEL') NOT NULL,
  `submitted_by` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `base_revision_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `candidate_revision_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `status` ENUM('PENDING','APPROVED','REJECTED','WITHDRAWN','EXPIRED') NOT NULL DEFAULT 'PENDING',
  `expires_at` DATETIME(6) NOT NULL,
  `resolved_by` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `resolved_at` DATETIME(6) NULL,
  `reason` VARCHAR(1000) NULL,
  `row_version` BIGINT UNSIGNED NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `pending_slot` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin GENERATED ALWAYS AS (CASE WHEN status='PENDING' THEN schedule_id ELSE NULL END) STORED,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_approval_proposals_1` (`pending_slot`),
  UNIQUE KEY `uq_approval_proposals_2` (`schedule_id`, `id`),
  KEY `ix_approval_proposals_1` (`status`, `expires_at`),
  KEY `ix_approval_proposals_2` (`submitted_by`, `created_at`),
  CONSTRAINT `ck_proposal_shape` CHECK ((kind='CREATE' AND base_revision_id IS NULL AND candidate_revision_id IS NOT NULL) OR (kind='CHANGE' AND base_revision_id IS NOT NULL AND candidate_revision_id IS NOT NULL AND base_revision_id <> candidate_revision_id) OR (kind='CANCEL' AND base_revision_id IS NOT NULL AND candidate_revision_id IS NULL)),
  CONSTRAINT `ck_proposal_resolution` CHECK ((status='PENDING' AND resolved_by IS NULL AND resolved_at IS NULL) OR (status IN ('APPROVED','REJECTED','WITHDRAWN') AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL) OR (status='EXPIRED' AND resolved_at IS NOT NULL)),
  CONSTRAINT `ck_proposal_no_self` CHECK (status NOT IN ('APPROVED','REJECTED') OR resolved_by <> submitted_by),
  CONSTRAINT `ck_proposal_withdraw` CHECK (status <> 'WITHDRAWN' OR resolved_by = submitted_by),
  CONSTRAINT `ck_proposal_reason` CHECK ((kind <> 'CANCEL' AND status NOT IN ('REJECTED','EXPIRED')) OR (reason IS NOT NULL AND CHAR_LENGTH(TRIM(reason)) > 0)),
  CONSTRAINT `fk_approval_proposals_1` FOREIGN KEY (`schedule_id`) REFERENCES `schedule_roots` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_approval_proposals_2` FOREIGN KEY (`submitted_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_approval_proposals_3` FOREIGN KEY (`resolved_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_approval_proposals_4` FOREIGN KEY (`schedule_id`, `base_revision_id`) REFERENCES `schedule_revisions` (`schedule_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_approval_proposals_5` FOREIGN KEY (`schedule_id`, `candidate_revision_id`) REFERENCES `schedule_revisions` (`schedule_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Định danh tài liệu theo cuộc họp; gỡ hiển thị có lý do
CREATE TABLE `meeting_documents` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `schedule_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `display_name` VARCHAR(255) NOT NULL,
  `is_hidden` BOOLEAN NOT NULL DEFAULT FALSE,
  `hidden_by` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `hidden_at` DATETIME(6) NULL,
  `hide_reason` VARCHAR(500) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_meeting_documents_1` (`schedule_id`, `id`),
  CONSTRAINT `ck_document_visibility` CHECK ((is_hidden=0 AND hidden_by IS NULL AND hidden_at IS NULL AND hide_reason IS NULL) OR (is_hidden=1 AND hidden_by IS NOT NULL AND hidden_at IS NOT NULL AND hide_reason IS NOT NULL AND CHAR_LENGTH(TRIM(hide_reason)) > 0)),
  CONSTRAINT `fk_meeting_documents_1` FOREIGN KEY (`schedule_id`) REFERENCES `schedule_roots` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_meeting_documents_2` FOREIGN KEY (`hidden_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Mỗi tệp là một phiên bản gắn ngữ cảnh bản lịch để kiểm tra quyền lịch sử
CREATE TABLE `document_versions` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `document_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `schedule_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `context_revision_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `version_no` INT UNSIGNED NOT NULL,
  `original_filename` VARCHAR(255) NOT NULL,
  `extension` ENUM('pdf','docx','pptx','xlsx','jpg','jpeg','png') NOT NULL,
  `mime_type` VARCHAR(120) NOT NULL,
  `size_bytes` INT UNSIGNED NOT NULL,
  `sha256` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `storage_key` VARCHAR(255) NOT NULL,
  `uploaded_by` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_document_versions_1` (`document_id`, `version_no`),
  UNIQUE KEY `uq_document_versions_2` (`storage_key`),
  CONSTRAINT `ck_file_size` CHECK (size_bytes BETWEEN 1 AND 20971520),
  CONSTRAINT `ck_file_version` CHECK (version_no > 0),
  CONSTRAINT `fk_document_versions_1` FOREIGN KEY (`schedule_id`, `document_id`) REFERENCES `meeting_documents` (`schedule_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_document_versions_2` FOREIGN KEY (`schedule_id`, `context_revision_id`) REFERENCES `schedule_revisions` (`schedule_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_document_versions_3` FOREIGN KEY (`uploaded_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Sự kiện email ghi cùng transaction nghiệp vụ; payload chỉ có ID và dữ liệu tối thiểu
CREATE TABLE `outbox_events` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `schedule_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `proposal_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `event_type` VARCHAR(64) NOT NULL,
  `dedupe_key` VARCHAR(150) NOT NULL,
  `payload` JSON NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_outbox_events_1` (`dedupe_key`),
  CONSTRAINT `fk_outbox_events_1` FOREIGN KEY (`schedule_id`) REFERENCES `schedule_roots` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_outbox_events_2` FOREIGN KEY (`schedule_id`, `proposal_id`) REFERENCES `approval_proposals` (`schedule_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Một người nhận một sự kiện; theo dõi và thử lại độc lập
CREATE TABLE `email_deliveries` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `event_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `recipient_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `status` ENUM('PENDING','PROCESSING','RETRY','SMTP_ACCEPTED','FAILED','SKIPPED') NOT NULL DEFAULT 'PENDING',
  `attempt_count` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  `next_attempt_at` DATETIME(6) NOT NULL,
  `first_failed_at` DATETIME(6) NULL,
  `lease_token` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `lease_until` DATETIME(6) NULL,
  `last_error_code` VARCHAR(80) NULL,
  `smtp_accepted_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_email_deliveries_1` (`event_id`, `recipient_user_id`),
  KEY `ix_email_deliveries_1` (`status`, `next_attempt_at`),
  KEY `ix_email_deliveries_2` (`status`, `lease_until`),
  CONSTRAINT `ck_delivery_attempts` CHECK (attempt_count <= 4),
  CONSTRAINT `ck_delivery_lease` CHECK ((status='PROCESSING' AND lease_token IS NOT NULL AND lease_until IS NOT NULL) OR (status<>'PROCESSING' AND lease_token IS NULL AND lease_until IS NULL)),
  CONSTRAINT `ck_delivery_accepted` CHECK ((status='SMTP_ACCEPTED' AND smtp_accepted_at IS NOT NULL) OR (status<>'SMTP_ACCEPTED' AND smtp_accepted_at IS NULL)),
  CONSTRAINT `fk_email_deliveries_1` FOREIGN KEY (`event_id`) REFERENCES `outbox_events` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_email_deliveries_2` FOREIGN KEY (`recipient_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Lưu vết lần gửi; STARTED có thể UNKNOWN khi Worker chết sau SMTP
CREATE TABLE `email_attempts` (
  `delivery_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `attempt_no` TINYINT UNSIGNED NOT NULL,
  `started_at` DATETIME(6) NOT NULL,
  `finished_at` DATETIME(6) NULL,
  `outcome` ENUM('STARTED','SMTP_ACCEPTED','ERROR','UNKNOWN') NOT NULL,
  `recipient_email` VARCHAR(254) NOT NULL,
  `safe_error_code` VARCHAR(80) NULL,
  PRIMARY KEY (`delivery_id`, `attempt_no`),
  CONSTRAINT `ck_attempt_no` CHECK (attempt_no BETWEEN 1 AND 4),
  CONSTRAINT `ck_attempt_finish` CHECK ((outcome='STARTED' AND finished_at IS NULL) OR (outcome<>'STARTED' AND finished_at IS NOT NULL)),
  CONSTRAINT `fk_email_attempts_1` FOREIGN KEY (`delivery_id`) REFERENCES `email_deliveries` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Lịch sử thao tác; không phải cơ chế phân quyền mặc định cho Admin
CREATE TABLE `audit_entries` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `action` VARCHAR(80) NOT NULL,
  `entity_type` VARCHAR(50) NOT NULL,
  `entity_id` VARCHAR(36) NOT NULL,
  `schedule_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `revision_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `safe_metadata` JSON NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `ix_audit_entries_1` (`schedule_id`, `created_at`),
  KEY `ix_audit_entries_2` (`actor_user_id`, `created_at`),
  CONSTRAINT `ck_audit_revision_scope` CHECK (revision_id IS NULL OR schedule_id IS NOT NULL),
  CONSTRAINT `fk_audit_entries_1` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_audit_entries_2` FOREIGN KEY (`schedule_id`) REFERENCES `schedule_roots` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_audit_entries_3` FOREIGN KEY (`schedule_id`, `revision_id`) REFERENCES `schedule_revisions` (`schedule_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Chống lặp cùng thao tác HTTP; lưu ID kết quả, không sao chép response riêng tư
CREATE TABLE `idempotency_keys` (
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `operation` VARCHAR(64) NOT NULL,
  `key_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `request_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `result_schedule_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `result_proposal_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `response_status` SMALLINT UNSIGNED NOT NULL,
  `expires_at` DATETIME(6) NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`user_id`, `operation`, `key_hash`),
  KEY `ix_idempotency_keys_1` (`expires_at`),
  CONSTRAINT `fk_idempotency_keys_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_idempotency_keys_2` FOREIGN KEY (`result_schedule_id`) REFERENCES `schedule_roots` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_idempotency_keys_3` FOREIGN KEY (`result_proposal_id`) REFERENCES `approval_proposals` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Thêm sau do quan hệ vòng lịch -> bản nội dung -> lịch.
ALTER TABLE schedule_roots ADD CONSTRAINT fk_root_current_same_schedule
 FOREIGN KEY (id, current_revision_id) REFERENCES schedule_revisions(schedule_id, id)
 ON DELETE RESTRICT ON UPDATE RESTRICT;

-- Duy nhất phiên bản current và chưa hủy mới là lịch hiệu lực.
CREATE SQL SECURITY INVOKER VIEW v_effective_schedules AS
 SELECT r.id AS schedule_id, r.created_by AS organizer_user_id, r.row_version,
        v.id AS revision_id, v.kind, v.starts_at, v.ends_at,
        v.room_id, v.chair_user_id, v.department_id
 FROM schedule_roots r JOIN schedule_revisions v
 ON v.schedule_id=r.id AND v.id=r.current_revision_id
 WHERE r.cancelled_at IS NULL;

-- Chọn cấu hình hiệu lực tại giờ bắt đầu họp; không dùng cấu hình hiện tại tính ngược lịch sử.
CREATE SQL SECURITY INVOKER VIEW v_effective_meetings AS
 SELECT e.*, p.id AS policy_id, p.capacity, p.buffer_minutes,
        TIMESTAMPADD(MINUTE,p.buffer_minutes,e.ends_at) AS blocked_until
 FROM v_effective_schedules e JOIN room_policy_versions p ON p.room_id=e.room_id
 AND p.effective_from <= e.starts_at
 AND NOT EXISTS (SELECT 1 FROM room_policy_versions p2 WHERE p2.room_id=p.room_id
                 AND p2.effective_from <= e.starts_at AND p2.effective_from > p.effective_from)
 WHERE e.kind='MEETING';

-- View không tự che quyền nội dung/người. API phải lọc và chiếu DTO theo người gọi.
CREATE SQL SECURITY INVOKER VIEW v_effective_participants AS
 SELECT e.schedule_id,e.revision_id,e.kind,e.starts_at,e.ends_at,p.user_id,p.is_required
 FROM v_effective_schedules e JOIN revision_participants p ON p.revision_id=e.revision_id;

INSERT INTO schema_migrations(version) VALUES ('001_baseline');
