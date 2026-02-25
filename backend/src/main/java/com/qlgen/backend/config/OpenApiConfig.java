package com.qlgen.backend.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI qlgenOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("qlGen API")
                        .description("ICP-Driven Qualified Lead Generation API")
                        .version("0.1.0"));
    }
}
