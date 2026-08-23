package com.ju_project.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.boot.autoconfigure.domain.EntityScan;

@Configuration
@EnableJpaRepositories(basePackages = "com.ju_project.repository")
@EntityScan(basePackages = "com.ju_project.entity")
public class JpaConfig {
}
