from ..models import Machine


def seed(ctx):
    """Fill in blank machine notes from the pack's MACHINE_NOTES."""
    for name, notes in ctx.pack.MACHINE_NOTES.items():
        Machine.objects.filter(name=name, notes="").update(notes=notes)
