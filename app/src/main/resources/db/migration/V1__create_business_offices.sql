-- V1: business_offices 테이블 생성 및 sentinel 데이터 삽입
CREATE TABLE IF NOT EXISTS business_offices (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    office_code VARCHAR(50) NOT NULL UNIQUE,
    office_name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('HEADQUARTER', 'BRANCH', 'SUB_OFFICE')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- sentinel 데이터: 가상 사업소 A, B, C
INSERT INTO business_offices (office_code, office_name, type, created_at)
VALUES ('OFF-A', '가상사업소 A', 'BRANCH', CURRENT_TIMESTAMP);

INSERT INTO business_offices (office_code, office_name, type, created_at)
VALUES ('OFF-B', '가상사업소 B', 'BRANCH', CURRENT_TIMESTAMP);

INSERT INTO business_offices (office_code, office_name, type, created_at)
VALUES ('OFF-C', '가상사업소 C', 'SUB_OFFICE', CURRENT_TIMESTAMP);
