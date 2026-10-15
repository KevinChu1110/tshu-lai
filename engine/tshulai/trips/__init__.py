"""旅行足跡：家人丟進 trips/ 的照片 → 讀 EXIF 時間與 GPS → 反查地名 → 依日期分組成「一趟」。

用途兩個：
1. 阿嬤看板（給真的阿嬤看的平板畫面）顯示「阿融最近去哪裡玩」
2. 寫進記憶，讓數位阿嬤會問「你頂禮拜去淡水，好耍無？」
"""

from .exif import PhotoMeta, read_photo_meta
from .geocode import Geocoder, NominatimGeocoder, NullGeocoder
from .trips import Trip, group_trips, scan_trips

__all__ = ["PhotoMeta", "read_photo_meta", "Geocoder", "NominatimGeocoder", "NullGeocoder", "Trip", "group_trips", "scan_trips"]
