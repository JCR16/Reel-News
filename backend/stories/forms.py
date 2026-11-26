from django import forms
from stories.models import Story, Tag

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

class RevisionRejectionForm(forms.Form):
    """
    Collect feedback explaining why a revision was rejected.
    """

    # Track which revision the administrator intends to reject.
    expected_revision_num = forms.IntegerField(
        widget=forms.HiddenInput(),
        min_value=1,
        required=True,
    )

    feedback = forms.CharField(
        label="Reason for Rejection",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": (
                    "Explain what needs improvement in the "
                    "headline or summary..."
                ),
            }
        ),
        required=True,
        help_text=(
            "This feedback will be provided to Gemini "
            "when regenerating the revision."
        ),
    )


class TagAdminForm(forms.ModelForm):
    """
    Validate tag names to prevent duplicate tags.
    """

    class Meta:
        model = Tag
        fields = "__all__"

    def clean_name(self):
        # Remove leading and trailing whitespace.
        name = self.cleaned_data["name"].strip()

        # Check for existing tags with the same name,
        # ignoring capitalization.
        existing_tags = Tag.objects.filter(
            name__iexact=name
        )

        # Exclude the current tag when editing an existing one.
        if self.instance.pk:
            existing_tags = existing_tags.exclude(
                pk=self.instance.pk
            )

        if existing_tags.exists():
            raise forms.ValidationError(
                "A tag with this name already exists."
            )

        return name


class StoryAdminForm(forms.ModelForm):
    """
    Add an editable review feedback field to the Story Admin form.
    """
    # Track which revision was current when the form was opened.
    editing_revision = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=False,
    )

    # Track the revision status when the administrator opens the form.
    editing_revision_status = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
    )

    review_feedback = forms.CharField(
        label="Current Revision Review Feedback",
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        help_text="Feedback used when regenerating a rejected revision.",
    )

    # Allow administrators to assign multiple tags to a story.
    # The available choices come from the Tag table.
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all().order_by("name"),
        widget=forms.SelectMultiple(attrs={"size": 8}),
        required=False,
        label="Story Tags",
        help_text="Hold Ctrl (or Cmd on Mac) to select multiple tags.",
    )

    class Meta:
        model = Story
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Preselect the tags already associated with this story.
        if self.instance.pk and "tags" in self.fields:
            self.fields["tags"].initial = Tag.objects.filter(
                story_links__storyid=self.instance
            )

        # Record the revision number when opening an editable form.
        if self.instance.pk and "editing_revision" in self.fields:
            self.fields["editing_revision"].initial = (
                self.instance.currentrevisionnum
            )

        # Retrieve the current revision.
        if self.instance.pk and self.instance.currentrevisionnum:
            revision = self.instance.revisions.filter(
                revisionnum=self.instance.currentrevisionnum
            ).first()

            if revision:
                # Store the revision status for stale-form validation.
                if "editing_revision_status" in self.fields:
                    self.fields["editing_revision_status"].initial = (
                        revision.status
                    )

                # Populate editable feedback when the field is available.
                if "review_feedback" in self.fields:
                    self.fields["review_feedback"].initial = (
                        revision.reviewfeedback or ""
                    )

                    # Only rejected revisions can have editable feedback.
                    if revision.status != "Rejected":
                        self.fields["review_feedback"].disabled = True

    def clean(self):
        """
        Prevent saving an outdated Story form if another administrator
        has created a newer revision since the page was opened.
        """

        # Run Django's normal form validation first.
        cleaned_data = super().clean()

        # Only check existing stories.
        if not self.instance.pk:
            return cleaned_data

        # Revision number submitted by the browser.
        editing_revision = cleaned_data.get("editing_revision")

        # Retrieve the latest revision number directly from the database.
        current_revision = (
            Story.objects
            .values_list("currentrevisionnum", flat=True)
            .get(pk=self.instance.pk)
        )

        # Reject forms that were opened before a newer revision existed.
        if editing_revision != current_revision:
            raise forms.ValidationError(
                "This story has been updated since you opened this page. "
                "Please refresh the page before saving your changes."
            )

        # Retrieve the current revision's latest status.
        revision = self.instance.revisions.filter(
            revisionnum=current_revision
        ).first()

        # Prevent saving if the revision status has changed.
        if (
            revision is None
            or cleaned_data.get("editing_revision_status") != revision.status
        ):
            raise forms.ValidationError(
                "This story has been updated since you opened this page. "
                "Please refresh the page before saving your changes."
            )

        # Validate feedback eligibility before saving the story.
        if "review_feedback" in self.changed_data:

            # Retrieve the revision associated with the submitted form.
            revision = self.instance.revisions.filter(
                revisionnum=editing_revision
            ).first()

            # Only rejected revisions can have their feedback modified.
            if revision is None or revision.status != "Rejected":
                raise forms.ValidationError(
                    "Review feedback can only be updated "
                    "on Rejected revisions."
                )

        return cleaned_data