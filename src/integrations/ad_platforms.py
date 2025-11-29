class GoogleAdsService:
    def __init__(self):
        pass

    def upload_conversion(self, gclid, conversion_name, value):
        print(f"Mock Google Ads Upload: {gclid}, {conversion_name}, {value}")
        return True

class FacebookAdsService:
    def __init__(self):
        pass

    def upload_event(self, pixel_id, event_name, data):
        print(f"Mock FB Event Upload: {pixel_id}, {event_name}, {data}")
        return True
