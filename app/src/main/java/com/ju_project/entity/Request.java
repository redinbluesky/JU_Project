package com.ju_project.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;
import java.time.ZonedDateTime;

@Entity
@Table(name = "requests")
public class Request {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "request_no_seq", nullable = false, unique = true)
    private Long requestNoSeq;

    @Column(name = "office_id")
    private Long officeId;

    @Column(name = "item_name")
    private String itemName;

    @Column(name = "quantity")
    private Integer quantity;

    @Column(name = "status")
    private String status;

    @Column(name = "created_at")
    private ZonedDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        this.createdAt = ZonedDateTime.now();
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getRequestNoSeq() { return requestNoSeq; }
    public void setRequestNoSeq(Long requestNoSeq) { this.requestNoSeq = requestNoSeq; }
    public Long getOfficeId() { return officeId; }
    public void setOfficeId(Long officeId) { this.officeId = officeId; }
    public String getItemName() { return itemName; }
    public void setItemName(String itemName) { this.itemName = itemName; }
    public Integer getQuantity() { return quantity; }
    public void setQuantity(Integer quantity) { this.quantity = quantity; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public ZonedDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(ZonedDateTime createdAt) { this.createdAt = createdAt; }
}
