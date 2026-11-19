from django import forms

class ArticleInputForm(forms.Form):
    """
    Collect the information needed to generate a story
    from a single source article.
    """

    # Basic information about the article.
    title = forms.CharField(max_length=255)
    link = forms.URLField()

    # Select an existing publisher from PostgreSQL.
    publisher = forms.ModelChoiceField(
        queryset=None,
    )

    # Article content passed to Gemini (not stored permanently).
    text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8}),
    )

    def __init__(self, *args, **kwargs):
        from .models import Publisher

        super().__init__(*args, **kwargs)

        # Populate the publisher dropdown from our database.
        self.fields["publisher"].queryset = Publisher.objects.order_by("name")

# A formset lets us collect multiple articles in one submission.
ArticleFormSet = forms.formset_factory(
    ArticleInputForm,
    extra=1,
    min_num=1,
    validate_min=True,
)