# =============================================================================
# ASAP Results Analysis: AI-Human Rater Agreement Across Treatments
# Single model — sq_error outcome, prompt_name as question covariate
# =============================================================================

# ---- 0. Setup ---------------------------------------------------------------

required_packages <- c("lme4", "lmerTest", "emmeans", "dplyr", "tidyr",
                       "flextable", "officer", "broom.mixed", "readr")
to_install <- required_packages[!sapply(required_packages, requireNamespace, quietly = TRUE)]
if (length(to_install) > 0) install.packages(to_install)

library(lme4)
library(lmerTest)
library(emmeans)
library(dplyr)
library(tidyr)
library(flextable)
library(officer)
library(broom.mixed)
library(readr)

set.seed(2026)

# ---- File paths: EDIT IF NEEDED ---------------------------------------------
item_level_path <- "/home/simao/ThesisTesing/long_format_asap.csv"
output_docx     <- "asap_results_tables_v2.docx"

# ---- Helpers ----------------------------------------------------------------
resolve_cols <- function(df) {
    nms <- names(df)
    list(
        lcl = nms[grepl("LCL|lower\\.CL|lower\\.cl", nms, ignore.case = FALSE)][1],
        ucl = nms[grepl("UCL|upper\\.CL|upper\\.cl", nms, ignore.case = FALSE)][1],
        t   = nms[grepl("t\\.ratio|z\\.ratio|statistic", nms, ignore.case = FALSE)][1],
        p   = nms[grepl("p\\.value", nms, ignore.case = FALSE)][1]
    )
}

fmt_p <- function(p) ifelse(p < .001, "< .001", sprintf("%.3f", p))

sig_stars <- function(p) {
    ifelse(p < .001, "***",
    ifelse(p < .01,  "**",
    ifelse(p < .05,  "*",
    ifelse(p < .1,   ".", ""))))
}

# =============================================================================
# 1. Load and prepare data
# =============================================================================

raw <- read_csv(item_level_path, show_col_types = FALSE)

cat(sprintf("Rows loaded: %d\n", nrow(raw)))
cat(sprintf("Columns: %s\n", paste(names(raw), collapse = ", ")))

# Drop grading failures
n_before <- nrow(raw)
dat <- raw %>% filter(AI_grade != -1, !is.na(AI_grade), !is.na(score))
cat(sprintf("Dropped %d rows with AI_grade == -1 / NA or missing score.\n",
            n_before - nrow(dat)))

# Compute squared error (same as original script)
dat <- dat %>% mutate(sq_error = (AI_grade - score)^2)

# Factorise
dat$treatment   <- factor(dat$treatment)
dat$treatment   <- relevel(dat$treatment, ref = "MAS-BASELINE")
dat$essay_id    <- factor(dat$essay_id)
dat$prompt_name <- factor(dat$prompt_name)   # question covariate

cat(sprintf("\nFinal analytic N: %d rows | %d unique essays | %d treatments | %d prompts\n",
            nrow(dat), nlevels(dat$essay_id),
            nlevels(dat$treatment), nlevels(dat$prompt_name)))
cat("Treatment levels (reference = MAS-BASELINE):\n")
print(levels(dat$treatment))
cat("\nPrompt names:\n")
print(levels(dat$prompt_name))

# =============================================================================
# 2. Primary mixed model
# =============================================================================
# sq_error ~ treatment + prompt_name + (1 | essay_id)
#   treatment:   fixed effect of interest (14 contrasts vs MAS-BASELINE)
#   prompt_name: additive nuisance — different tasks have different difficulty
#   (1|essay_id): same essay appears once per treatment; absorbs essay difficulty

cat("\nFitting primary model: sq_error ~ treatment + prompt_name + (1 | essay_id) ...\n")

m1 <- lmer(
    sq_error ~ treatment + prompt_name + (1 | essay_id),
    data = dat,
    REML = TRUE
)

cat("\n--- Primary model summary ---\n")
print(summary(m1))

cat("\n--- Convergence check ---\n")
print(m1@optinfo$conv$lme4)

saveRDS(m1, "primary_model_asap_v2.rds")

get_coef_table <- function(model) {
    s  <- summary(model)
    ct <- as.data.frame(s$coefficients)
    ct$term <- rownames(ct)
    rownames(ct) <- NULL
    names(ct) <- c("estimate", "se", "df", "t_value", "p_value", "term")
    ct[, c("term", "estimate", "se", "df", "t_value", "p_value")]
}

# =============================================================================
# 3. TABLE 1: SAS-BASELINE vs MAS-BASELINE
# =============================================================================

emm_sas <- emmeans(m1, ~ treatment,
                   at = list(treatment = c("MAS-BASELINE", "SAS-BASELINE")))
sas_contrasts   <- contrast(emm_sas, method = list("SAS - MAS" = c(-1, 1)))
sas_contrast_df <- as.data.frame(summary(sas_contrasts, infer = c(TRUE, TRUE)))

cat("\n--- Table 1: SAS-BASELINE vs MAS-BASELINE ---\n")
print(sas_contrast_df)

cols1 <- resolve_cols(sas_contrast_df)

table1 <- sas_contrast_df %>%
    transmute(
        Contrast       = "SAS-BASELINE vs MAS-BASELINE",
        Estimate       = round(estimate, 4),
        SE             = round(SE, 4),
        df             = round(df, 1),
        `95% CI Lower` = round(.data[[cols1$lcl]], 4),
        `95% CI Upper` = round(.data[[cols1$ucl]], 4),
        `t value`      = round(.data[[cols1$t]], 3),
        `p value`      = fmt_p(.data[[cols1$p]]),
        Sig            = sig_stars(.data[[cols1$p]]),
        Interpretation = ifelse(estimate < 0,
                                "SAS lower error (improvement)",
                                "SAS higher error (worse)")
    )

cat("\n--- Table 1 (formatted) ---\n")
print(table1)

# =============================================================================
# 4. TABLE 2: Omnibus Type III ANOVA
# =============================================================================

anova_m1 <- anova(m1, type = 3)
cat("\n--- ANOVA (Type III, Satterthwaite) ---\n")
print(anova_m1)

anova_df <- as.data.frame(anova_m1)
anova_df$Term <- rownames(anova_df)
rownames(anova_df) <- NULL

table2 <- anova_df %>%
    transmute(
        Term,
        `Sum Sq`  = round(`Sum Sq`, 2),
        `Mean Sq` = round(`Mean Sq`, 3),
        NumDF     = round(NumDF, 0),
        DenDF     = round(DenDF, 1),
        F         = round(`F value`, 3),
        p         = fmt_p(`Pr(>F)`)
    )

cat("\n--- Table 2 (formatted) ---\n")
print(table2)

# =============================================================================
# 5. TOST equivalence margin
# =============================================================================
# Half the SD of MAS-BASELINE sq_error cell means per prompt,
# matching the original script's cross-cell SD logic

mas_cells <- dat %>%
    filter(treatment == "MAS-BASELINE") %>%
    group_by(prompt_name) %>%
    summarise(cell_mean_sqerr = mean(sq_error), .groups = "drop")

cat("\n--- MAS-BASELINE cell means per prompt (used for TOST margin) ---\n")
print(mas_cells)

noise_sd    <- sd(mas_cells$cell_mean_sqerr)
tost_margin <- noise_sd / 2

cat(sprintf("\nMAS-BASELINE cross-prompt SD: %.4f\n", noise_sd))
cat(sprintf("TOST equivalence margin (half SD): %.4f\n", tost_margin))

# =============================================================================
# 6. TABLES 3 & 4: Equivalence tests (TOST)
# =============================================================================

run_tost <- function(model, treat_a, treat_b, margin, conf_level = 0.90) {
    emm <- emmeans(model, ~ treatment, at = list(treatment = c(treat_a, treat_b)))
    con <- contrast(emm, method = list("diff" = c(-1, 1)))
    s   <- as.data.frame(summary(con, infer = c(TRUE, TRUE), level = conf_level))

    cols <- resolve_cols(s)

    est <- s$estimate;  se <- s$SE;  df <- s$df
    lcl <- s[[cols$lcl]];  ucl <- s[[cols$ucl]]

    t_lower <- (est - (-margin)) / se
    t_upper <- (est -   margin)  / se
    p_lower <- 1 - pt(t_lower, df)
    p_upper <-     pt(t_upper, df)
    p_tost  <- max(p_lower, p_upper)

    equivalent <- (lcl > -margin) & (ucl < margin)

    data.frame(
        Comparison          = paste0(treat_b, " vs ", treat_a),
        Estimate            = round(est, 4),
        SE                  = round(se,  4),
        df                  = round(df,  1),
        `Margin (+/-)`      = round(margin, 4),
        `90% CI Lower`      = round(lcl, 4),
        `90% CI Upper`      = round(ucl, 4),
        `TOST p value`      = fmt_p(p_tost),
        `Equivalent at 90%` = ifelse(equivalent, "Yes", "No"),
        check.names = FALSE
    )
}

table3 <- run_tost(m1, "MAS-BASELINE", "MAS-H2a", tost_margin)
table4 <- run_tost(m1, "MAS-BASELINE", "MAS-H2b", tost_margin)

cat("\n--- Table 3: Equivalence MAS-BASELINE vs MAS-H2a ---\n"); print(table3)
cat("\n--- Table 4: Equivalence MAS-BASELINE vs MAS-H2b ---\n"); print(table4)

# =============================================================================
# 7. TABLE 5: All main treatments vs MAS-BASELINE
# =============================================================================

main_treatments <- c("H1a", "H1b", "H1c", "LocalSuggest", "LocalRevise",
                     "GLobalsuggest", "globalrevise")

coef_tbl <- get_coef_table(m1)

table5 <- coef_tbl %>%
    filter(term %in% paste0("treatment", main_treatments)) %>%
    mutate(
        Treatment      = sub("^treatment", "", term),
        Estimate       = round(estimate, 4),
        SE             = round(se, 4),
        df             = round(df, 1),
        `t value`      = round(t_value, 3),
        `p value`      = fmt_p(p_value),
        Sig            = sig_stars(p_value),
        Interpretation = ifelse(estimate < 0,
                                "Lower error vs MAS-BASELINE (improvement)",
                                "Higher error vs MAS-BASELINE (worse)")
    ) %>%
    select(Treatment, Estimate, SE, df, `t value`, `p value`, Sig, Interpretation)

cat("\n--- Table 5: Main treatments vs MAS-BASELINE ---\n")
print(table5)

# =============================================================================
# 8. TABLE 6: Post-hoc pairwise contrasts (contra pairs, Holm-adjusted)
# =============================================================================

posthoc_pairs <- list(
    c("H1acontra",  "H1a"),
    c("H1bcontra2", "H1bcontra"),
    c("H1Ccontra",  "H1c")
)

run_pairwise <- function(model, treat_a, treat_b) {
    emm <- emmeans(model, ~ treatment, at = list(treatment = c(treat_a, treat_b)))
    con <- contrast(emm, method = list("diff" = c(-1, 1)))
    s   <- as.data.frame(summary(con, infer = c(TRUE, TRUE)))
    cols <- resolve_cols(s)
    data.frame(
        Comparison     = paste0(treat_b, " vs ", treat_a),
        Estimate       = round(s$estimate, 4),
        SE             = round(s$SE, 4),
        df             = round(s$df, 1),
        `95% CI Lower` = round(s[[cols$lcl]], 4),
        `95% CI Upper` = round(s[[cols$ucl]], 4),
        `t value`      = round(s[[cols$t]], 3),
        `p value`      = fmt_p(s[[cols$p]]),
        Sig            = sig_stars(s[[cols$p]]),
        check.names    = FALSE
    )
}

table6_raw <- lapply(posthoc_pairs, function(pair) run_pairwise(m1, pair[1], pair[2]))
table6 <- bind_rows(table6_raw)

p_numeric <- ifelse(table6$`p value` == "< .001", 0.0001, as.numeric(table6$`p value`))
table6$`p value (Holm-adjusted)` <- fmt_p(p.adjust(p_numeric, method = "holm"))

cat("\n--- Table 6: Post-hoc pairwise contrasts (Holm-adjusted) ---\n")
print(table6)

# =============================================================================
# 9. TABLE 7: QWK per treatment x prompt
# =============================================================================

# Quadratic weighted kappa computed from scratch —
# no external package needed, works directly on numeric grade vectors.
compute_qwk <- function(actual, predicted) {
    # Build confusion matrix over the union of observed levels
    grades  <- sort(unique(c(actual, predicted)))
    n       <- length(grades)
    mat     <- matrix(0, nrow = n, ncol = n,
                      dimnames = list(grades, grades))
    for (i in seq_along(actual)) {
        r <- as.character(actual[i])
        c <- as.character(predicted[i])
        mat[r, c] <- mat[r, c] + 1
    }

    # Weight matrix: w_ij = (i - j)^2 / (n - 1)^2
    wt <- outer(seq_len(n), seq_len(n),
                function(i, j) (i - j)^2 / (n - 1)^2)

    row_sum <- rowSums(mat)
    col_sum <- colSums(mat)
    total   <- sum(mat)

    # Expected matrix under independence
    expected <- outer(row_sum, col_sum) / total

    numerator   <- sum(wt * mat)       / total
    denominator <- sum(wt * expected)  / total

    1 - numerator / denominator
}

table7 <- dat %>%
    group_by(Treatment = treatment, Prompt = prompt_name) %>%
    summarise(
        N   = n(),
        QWK = round(compute_qwk(score, AI_grade), 3),
        .groups = "drop"
    ) %>%
    arrange(Treatment, Prompt)

cat("\n--- Table 7: QWK per treatment x prompt ---\n")
print(table7)

# =============================================================================
# 10. Write to Word document
# =============================================================================

make_ft <- function(df, caption) {
    ft <- flextable(df)
    ft <- set_caption(ft, caption)
    ft <- theme_box(ft)
    ft <- fontsize(ft, size = 9, part = "all")
    ft <- bold(ft, part = "header")
    ft <- autofit(ft)
    ft
}

doc <- read_docx()

doc <- doc %>%
    body_add_par("Results Tables — ASAP Dataset", style = "heading 1") %>%
    body_add_par(paste0(
        "Generated from a linear mixed-effects model: ",
        "sq_error ~ treatment + prompt_name + (1 | essay_id), ",
        "fit with lme4::lmer() and lmerTest for Satterthwaite-approximated degrees of freedom. ",
        "sq_error = (AI_grade - score)^2, where score is the human expert grade. ",
        "MAS-BASELINE is the reference level for treatment. ",
        "prompt_name is included as an additive nuisance covariate to control for ",
        "task difficulty differences across the 6 prompts. ",
        "The random intercept (1 | essay_id) accounts for each essay appearing ",
        "once per treatment."
    ), style = "Normal") %>%
    body_add_par("", style = "Normal") %>%

    body_add_par("Table 1. SAS-BASELINE vs MAS-BASELINE", style = "heading 2") %>%
    body_add_flextable(make_ft(table1, "Table 1. SAS-BASELINE vs MAS-BASELINE")) %>%
    body_add_par("", style = "Normal") %>%

    body_add_par("Table 2. Omnibus Type III ANOVA", style = "heading 2") %>%
    body_add_par("Type III ANOVA with Satterthwaite df for all fixed effects.", style = "Normal") %>%
    body_add_flextable(make_ft(table2, "Table 2. Omnibus Type III ANOVA")) %>%
    body_add_par("", style = "Normal") %>%

    body_add_par("Table 3. Equivalence Test: MAS-BASELINE vs MAS-H2a", style = "heading 2") %>%
    body_add_par(sprintf("TOST margin = %.4f (half the SD of MAS-BASELINE cross-prompt cell means).",
                         tost_margin), style = "Normal") %>%
    body_add_flextable(make_ft(table3, "Table 3. TOST equivalence: MAS-BASELINE vs MAS-H2a")) %>%
    body_add_par("", style = "Normal") %>%

    body_add_par("Table 4. Equivalence Test: MAS-BASELINE vs MAS-H2b", style = "heading 2") %>%
    body_add_flextable(make_ft(table4, "Table 4. TOST equivalence: MAS-BASELINE vs MAS-H2b")) %>%
    body_add_par("", style = "Normal") %>%

    body_add_par("Table 5. Main Treatments vs MAS-BASELINE", style = "heading 2") %>%
    body_add_flextable(make_ft(table5,
        "Table 5. H1a, H1b, H1c, LocalSuggest, LocalRevise, GLobalsuggest, globalrevise vs MAS-BASELINE")) %>%
    body_add_par("", style = "Normal") %>%

    body_add_par("Table 6. Post-Hoc Pairwise Contrasts", style = "heading 2") %>%
    body_add_par("Holm-corrected across the 3 contra-pair comparisons.", style = "Normal") %>%
    body_add_flextable(make_ft(table6,
        "Table 6. Post-hoc: H1a vs H1acontra; H1bcontra vs H1bcontra2; H1Ccontra vs H1c")) %>%
    body_add_par("", style = "Normal") %>%

    body_add_par("Table 7. Descriptive Summary of Squared Error per Treatment x Prompt",
                 style = "heading 2") %>%
    body_add_flextable(make_ft(table7,
        "Table 7. Mean squared error by treatment and prompt"))

print(doc, target = output_docx)
cat(sprintf("\nWord document written to: %s\n", output_docx))

# =============================================================================
# 11. Save all tables as CSVs
# =============================================================================

write_csv(table1, "asap_table1_sas_vs_mas.csv")
write_csv(table2, "asap_table2_omnibus_anova.csv")
write_csv(table3, "asap_table3_equivalence_h2a.csv")
write_csv(table4, "asap_table4_equivalence_h2b.csv")
write_csv(table5, "asap_table5_main_treatments_vs_mas.csv")
write_csv(table6, "asap_table6_posthoc.csv")
write_csv(table7, "asap_table7_descriptive.csv")

cat("All tables also saved as individual CSV files.\n")
