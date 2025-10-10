-- db_config/01_seed_reference.sql

-- -----------------------------------------------------------
-- Initial Seeding for Small Reference Tables (skin_types)
-- -----------------------------------------------------------

-- Insert base skin types
INSERT INTO skin_types (skin_type_name) VALUES
('Normal'),
('Dry'),
('Oily'),
('Combination'),
('Sensitive'),
('Acne-Prone'),
('Mature'),
('ALL Skin Types')
ON CONFLICT (skin_type_name) DO NOTHING;