-- V3: request_status_history 테이블 생성
CREATE TABLE IF NOT EXISTS request_status_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    request_id BIGINT NOT NULL,
    from_status VARCHAR(50),
    to_status VARCHAR(50) NOT NULL CHECK (to_status IN ('PENDING', 'APPROVED', 'REJECTED', 'COMPLETED')),
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT fk_status_history_request FOREIGN KEY (request_id) REFERENCES requests(id)
);

CREATE INDEX IF NOT EXISTS idx_status_history_request_id ON request_status_history(request_id);
