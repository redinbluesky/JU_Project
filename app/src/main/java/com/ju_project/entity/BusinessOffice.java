package com.ju_project.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;
import java.time.ZonedDateTime;

@Entity
@Table(name = "business_offices")
public class BusinessOffice {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "office_code", nullable = false, unique = true)
    private String officeCode;

    @Column(name = "office_name", nullable = false)
    private String officeName;

    @Column(name = "type", nullable = false)
    private String type;

    @Column(name = "created_at")
    private ZonedDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        this.createdAt = ZonedDateTime.now();
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getOfficeCode() { return officeCode; }
    public void setOfficeCode(String officeCode) { this.officeCode = officeCode; }
    public String getOfficeName() { return officeName; }
    public void setOfficeName(String officeName) { this.officeName = officeName; }
    public String getType() { return type; }
    public void setType(String type) { this.type = type; }
    public ZonedDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(ZonedDateTime createdAt) { this.createdAt = createdAt; }
}
