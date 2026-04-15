from django.contrib import admin

from apps.documents.models import DocumentType, EmployeeDocument, MandatoryDocumentRule

admin.site.register(DocumentType)
admin.site.register(MandatoryDocumentRule)
admin.site.register(EmployeeDocument)

