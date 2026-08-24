from services.badge.renderers.base_renderer import BaseRenderer


class BadgeGenerationService:
    """
    Service responsible for generating badge images.
    """

    def __init__(self):
        pass

    def generate_badge(
        self,
        badge,
    ):
        """
        Generate badge image based on badge shape.

        Args:
            badge: BadgeDetails object

        Returns:
            PIL.Image.Image
        """

        renderer = BaseRenderer.get_renderer(
            badge.badge_shape
        )

        image = renderer.render_badge(
            badge
        )

        return image

    def generate_and_save_badge(
        self,
        badge,
        output_path,
    ):
        """
        Generate badge and save to disk.

        Args:
            badge: BadgeDetails object
            output_path: Output image path

        Returns:
            output_path
        """

        renderer = BaseRenderer.get_renderer(
            badge.badge_shape
        )

        image = renderer.render_badge(
            badge
        )

        renderer.save(
            image=image,
            output_path=output_path,
        )

        return output_path