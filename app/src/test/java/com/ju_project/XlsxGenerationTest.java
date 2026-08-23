package com.ju_project;

import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.junit.jupiter.api.*;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;

import static org.junit.jupiter.api.Assertions.*;

class XlsxGenerationTest {

    @Test
    void poiGeneratesValidXlsx() throws IOException {
        File xlsxFile = new File("runtime/xlsx/test-report.xlsx");

        try (Workbook workbook = new XSSFWorkbook()) {
            Sheet sheet = workbook.createSheet("Report");

            // 헤더 10개
            String[] headers = new String[]{
                "번호", "품목명", "수량", "상태", "접수일",
                "처리일", "담당자", "사업소", "비고", "확인"
            };

            Row headerRow = sheet.createRow(0);
            for (int i = 0; i < headers.length; i++) {
                Cell cell = headerRow.createCell(i);
                cell.setCellValue(headers[i]);
            }

            // 데이터 행 0개 (빈 결과)
            assertEquals(1, sheet.getPhysicalNumberOfRows(), "헤더 1행만 존재");

            try (FileOutputStream fos = new FileOutputStream(xlsxFile)) {
                workbook.write(fos);
            }
        }

        assertTrue(xlsxFile.exists(), "XLSX 파일이 생성되어야 함");
        assertTrue(xlsxFile.length() > 0, "XLSX 파일이 비어서는 안 됨");

        // 다시 열어 검증
        try (Workbook loaded = new XSSFWorkbook(new FileInputStream(xlsxFile))) {
            Sheet loadedSheet = loaded.getSheetAt(0);
            assertEquals(1, loadedSheet.getPhysicalNumberOfRows(), "1행만 존재");

            Row headerRow = loadedSheet.getRow(0);
            assertNotNull(headerRow);
            assertEquals(10, headerRow.getPhysicalNumberOfCells(), "헤더 10개");
        }
    }

    @Test
    void formulaInjectionStringsAreTextCells() throws IOException {
        File xlsxFile = new File("runtime/xlsx/formula-test.xlsx");

        try (Workbook workbook = new XSSFWorkbook()) {
            Sheet sheet = workbook.createSheet("Test");

            // 수식 주입 문자열들
            String[] formulaStrings = new String[]{
                "=1+1", "+1+1", "-1+1", "@1+1",
                "=\"1+1\"", "=SUM(A1:A10)", "=IF(A1>0,\"Y\",\"N\")"
            };

            Row row = sheet.createRow(0);
            for (int i = 0; i < formulaStrings.length; i++) {
                Cell cell = row.createCell(i);
                cell.setCellValue(formulaStrings[i]);
                assertEquals(CellType.STRING, cell.getCellType(),
                    "셀 " + i + "은 TEXT/String 타입이어야 함");
            }

            try (FileOutputStream fos = new FileOutputStream(xlsxFile)) {
                workbook.write(fos);
            }
        }

        assertTrue(xlsxFile.exists());

        // 다시 열어 검증
        try (Workbook loaded = new XSSFWorkbook(new FileInputStream(xlsxFile))) {
            Sheet loadedSheet = loaded.getSheetAt(0);
            Row loadedRow = loadedSheet.getRow(0);

            for (int i = 0; i < formulaStrings.length; i++) {
                Cell cell = loadedRow.getCell(i);
                assertEquals(CellType.STRING, cell.getCellType(),
                    "셀 " + i + "은 TEXT/String 타입이어야 함");
                assertEquals(formulaStrings[i], cell.getStringCellValue(),
                    "셀 " + i + " 값이 일치해야 함");
            }
        }
    }
}
