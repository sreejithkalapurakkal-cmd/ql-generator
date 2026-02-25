package com.qlgen.backend.dto.request;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class BANTWeightsRequest {

    @NotNull
    @DecimalMin("0.0")
    @DecimalMax("1.0")
    private Double budget;

    @NotNull
    @DecimalMin("0.0")
    @DecimalMax("1.0")
    private Double authority;

    @NotNull
    @DecimalMin("0.0")
    @DecimalMax("1.0")
    private Double need;

    @NotNull
    @DecimalMin("0.0")
    @DecimalMax("1.0")
    private Double timeline;
}
