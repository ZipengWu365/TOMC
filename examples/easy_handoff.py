"""Run without a reader key; copy the resulting prompt into your model."""

from tomc import prepare_context

context = prepare_context(
    "The workshop now has 28 attendees. Room B is available but not booked.",
    "What should we arrange next?",
)
print(context.prompt)
# Or pass context.messages to your chosen reader client.
