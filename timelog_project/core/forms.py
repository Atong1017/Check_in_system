import datetime
from django import forms


class CorrectionForm(forms.Form):
    CORRECTION_TYPE = [
        ("missed_in", "補打上班卡"),
        ("missed_out", "補打下班卡"),
    ]

    correction_type = forms.ChoiceField(
        choices=CORRECTION_TYPE,
        label="補簽類型",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )
    date = forms.DateField(
        label="日期",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        initial=datetime.date.today,
    )
    time = forms.TimeField(
        label="時間（估計）",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        initial=datetime.time(9, 0),
    )
    note = forms.CharField(
        label="說明",
        widget=forms.Textarea(attrs={
            "rows": 3,
            "class": "form-control",
            "placeholder": "請說明忘記打卡的原因...",
        }),
    )
    proof = forms.ImageField(
        label="證明圖片",
        help_text="請上傳截圖或照片作為補簽依據",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
    )
