from riche_questionnaire_back_end.models.users_models import User


MEDIA_CONSTANTS = {
    "kanban": {
        "get_media_user": User,
    },
}


def invert_media_constants(media_constants):
    inverted_dict = {}
    for category, actions in media_constants.items():
        for action, media_class in actions.items():
            path = f"{category}/{action}"
            inverted_dict[media_class.__name__] = path
    return inverted_dict


MEDIA_CLASS_CONSTANTS = invert_media_constants(MEDIA_CONSTANTS)
