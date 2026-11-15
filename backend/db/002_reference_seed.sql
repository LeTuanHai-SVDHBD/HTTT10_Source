-- Dữ liệu giả lập danh mục. Chạy một lần sau 001, không tạo tài khoản đăng nhập.
USE httt10;
SET time_zone='+00:00';
START TRANSACTION;
INSERT INTO departments(id,code,name) VALUES
 ('10000000-0000-0000-0000-000000000001','HC','Hành chính'),
 ('10000000-0000-0000-0000-000000000002','CNTT','Công nghệ thông tin');
INSERT INTO meeting_rooms(id,code,name,location) VALUES
 ('20000000-0000-0000-0000-000000000001','A101','Phòng họp A101','Tầng 1 - Khu A'),
 ('20000000-0000-0000-0000-000000000002','B201','Phòng họp B201','Tầng 2 - Khu B');
INSERT INTO room_policy_versions(id,room_id,effective_from,capacity,buffer_minutes) VALUES
 ('30000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','2020-01-01 00:00:00',20,15),
 ('30000000-0000-0000-0000-000000000002','20000000-0000-0000-0000-000000000002','2020-01-01 00:00:00',8,15);
-- UUID() chỉ dùng cho khóa dữ liệu danh mục; ứng dụng tạo UUID trước ở Python.
INSERT INTO room_weekly_windows(id,policy_id,weekday,start_time,end_time)
 SELECT UUID(),p.id,d.weekday,w.start_time,w.end_time
 FROM room_policy_versions p
 CROSS JOIN (SELECT 1 weekday UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5) d
 CROSS JOIN (SELECT CAST('08:00:00' AS TIME) start_time,CAST('12:00:00' AS TIME) end_time
             UNION ALL SELECT '13:00:00','17:00:00') w
 WHERE p.id IN ('30000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000002');
INSERT INTO room_equipment(room_id,equipment_code,display_name,quantity) VALUES
 ('20000000-0000-0000-0000-000000000001','PROJECTOR','Máy chiếu',1),
 ('20000000-0000-0000-0000-000000000001','WHITEBOARD','Bảng trắng',1),
 ('20000000-0000-0000-0000-000000000002','TV','Màn hình trình chiếu',1);
COMMIT;
