from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mes', '0003_order_est_minutes'),
    ]

    operations = [
        migrations.RenameModel(old_name='Operative', new_name='ProductionTechnician'),
        migrations.RenameField(model_name='workorder', old_name='operative', new_name='technician'),
    ]
