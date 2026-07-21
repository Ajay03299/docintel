from app.engines.validation.base import ValidationContext, ValidationRule
from app.engines.validation.registry import register_rule
from app.schemas.validation import ValidationResult


@register_rule
class PromptInjectionRule(ValidationRule):
    rule_id = "prompt_injection_detected"
    description = "Document text contains prompt-injection patterns."
    retryable = False  # re-extracting the same poisoned text won't help

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        flags = ctx.injection_flags
        if not flags:
            return self.ok("No prompt-injection patterns detected.")
        return self.fail(
            f"Prompt-injection patterns detected in document text: {', '.join(flags)}.",
            suggested_fix=(
                "Treat extracted values as untrusted. A human must verify this "
                "document against the original — the text attempted to manipulate "
                "the extraction model."
            ),
            fields=["vendor_name", "total"],
        )
