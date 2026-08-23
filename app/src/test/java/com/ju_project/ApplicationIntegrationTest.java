package com.ju_project;

import com.ju_project.entity.BusinessOffice;
import org.flywaydb.core.Flyway;
import org.h2.Driver;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabaseBuilder;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabaseType;

import javax.sql.DataSource;
import java.io.File;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ApplicationIntegrationTest {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private Flyway flyway;

    @Test
    @Disabled("Requires file-based H2 setup - see runtime/db verification")
    void contextLoads() {
        // Flyway가 이미 적용됨
        assertNotNull(flyway);
    }

    @Test
    void h2FileDatabaseCreated() {
        File dbFile = new File("runtime/db/ju-project.mv.db");
        assertTrue(dbFile.exists(), "H2 file database should be created at runtime/db/ju-project.mv.db");
    }

    @Test
    void flywayMigrationsApplied() {
        // H2의 FLIGHTWAY_SCHEMA_HISTORY 테이블은 대문자로 저장됨
        List<Map<String, Object>> rows = jdbcTemplate.query(
            "SELECT script, executed_at FROM \"FLYWAY_SCHEMA_HISTORY\" ORDER BY executed_at",
            (rs, rowNum) -> Map.of(
                "script", rs.getString("script"),
                "executed_at", rs.getTimestamp("executed_at")
            )
        );

        assertNotNull(rows);
        assertEquals(3, rows.size(), "V1, V2, V3 마이그레이션이 모두 적용되어야 함");
    }

    @Test
    void businessOfficesDataExists() {
        List<Map<String, Object>> offices = jdbcTemplate.query(
            "SELECT office_code, office_name, type FROM business_offices ORDER BY office_code",
            (rs, rowNum) -> Map.of(
                "office_code", rs.getString("office_code"),
                "office_name", rs.getString("office_name"),
                "type", rs.getString("type")
            )
        );

        assertNotNull(offices);
        assertEquals(3, offices.size());
        assertEquals("OFF-A", offices.get(0).get("office_code"));
        assertEquals("OFF-B", offices.get(1).get("office_code"));
        assertEquals("OFF-C", offices.get(2).get("office_code"));
    }

    @Test
    void requestsTableExists() {
        List<Map<String, Object>> tables = jdbcTemplate.query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'PUBLIC' AND table_name = 'REQUESTS'",
            (rs, rowNum) -> Map.of("table_name", rs.getString("table_name"))
        );
        assertNotNull(tables);
        assertEquals(1, tables.size());
    }

    @Test
    void requestNoSeqSequenceExists() {
        List<Map<String, Object>> seqs = jdbcTemplate.query(
            "SELECT sequence_name FROM information_schema.sequences WHERE sequence_name = 'REQUEST_NO_SEQ'",
            (rs, rowNum) -> Map.of("sequence_name", rs.getString("sequence_name"))
        );
        assertNotNull(seqs);
        assertEquals(1, seqs.size());
    }

    @Test
    void requestStatusHistoryTableExists() {
        List<Map<String, Object>> tables = jdbcTemplate.query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'PUBLIC' AND table_name = 'REQUEST_STATUS_HISTORY'",
            (rs, rowNum) -> Map.of("table_name", rs.getString("table_name"))
        );
        assertNotNull(tables);
        assertEquals(1, tables.size());
    }
}
