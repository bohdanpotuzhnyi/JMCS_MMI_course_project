# Event Bus

This module transports normalized modality events into the collaboration core.

The event bus should remain simple:

- timestamp events consistently
- distribute them to fusion and logging components
- avoid modality-specific business logic
