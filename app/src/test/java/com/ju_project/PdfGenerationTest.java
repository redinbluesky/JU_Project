package com.ju_project;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.junit.jupiter.api.*;
import org.springframework.boot.test.context.SpringBootTest;

import java.io.File;
import java.io.IOException;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
class PdfGenerationTest {

    @Test
    void pdfBoxGeneratesValidPdf() throws IOException {
        File pdfFile = new File("runtime/pdf/test-document.pdf");

        try (PDDocument document = new PDDocument()) {
            PDPage page = new PDPage();
            document.addPage(page);

            try (PDPageContentStream contentStream = new PDPageContentStream(document, page)) {
                contentStream.beginText();
                contentStream.setFont(PDType1Font.HELVETICA, 12);
                contentStream.newLineAtOffset(50, 700);
                contentStream.showText("기술 프로토타입 — 공단 제출용 아님");
                contentStream.endText();
            }

            document.save(pdfFile);
        }

        assertTrue(pdfFile.exists(), "PDF 파일이 생성되어야 함");
        assertTrue(pdfFile.length() > 0, "PDF 파일이 비어서는 안 됨");

        // PDFBox로 다시 로드하여 유효성 검증
        try (PDDocument loaded = Loader.loadPDF(pdfFile)) {
            assertEquals(1, loaded.getNumberOfPages(), "PDF는 1페이지여야 함");
        }
    }
}
