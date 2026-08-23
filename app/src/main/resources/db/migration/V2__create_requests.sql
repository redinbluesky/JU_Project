-- V2: requests 테이블 생성 및 request_no_seq 시퀀스
CREATE TABLE IF NOT EXISTS requests (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    request_no_seq BIGINT NOT NULL UNIQUE,
    office_id BIGINT,
    item_name VARCHAR(200) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    status VARCHAR(50) NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'COMPLETED')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT fk_requests_office FOREIGN KEY (office_id) REFERENCES business_offices(id)
);

CREATE SEQUENCE IF NOT EXISTS request_no_seq START WITH 1 INCREMENT BY 1;

CREATE INDEX IF NOT EXISTS idx_requests_office_id ON requests(office_id);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
