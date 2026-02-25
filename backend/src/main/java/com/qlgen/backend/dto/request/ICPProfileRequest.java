package com.qlgen.backend.dto.request;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import lombok.Data;

import java.util.List;

@Data
public class ICPProfileRequest {

    @Valid
    @NotNull
    private ICPProfile icpProfile;

    @Valid
    @NotNull
    private BANTWeightsRequest bantWeights;

    @Min(1)
    @Max(50)
    private int maxResults = 25;

    @Data
    public static class ICPProfile {
        @NotEmpty(message = "At least one industry is required")
        @Size(max = 10, message = "Maximum 10 industries allowed")
        private List<@NotBlank String> industries;

        @NotNull
        @Valid
        private RangeDto companySizeRange;

        @NotNull
        @Valid
        private RangeDto revenueRange;

        @NotEmpty(message = "At least one geography is required")
        @Size(max = 20, message = "Maximum 20 geographies allowed")
        private List<@NotBlank String> geographies;

        private List<String> techStack;

        @Size(max = 15, message = "Maximum 15 keywords allowed")
        private List<String> keywords;

        @Size(max = 1000, message = "Additional notes cannot exceed 1000 characters")
        private String additionalNotes;
    }

    @Data
    public static class RangeDto {
        @Min(0)
        private long min;

        @Min(0)
        private long max;
    }
}
