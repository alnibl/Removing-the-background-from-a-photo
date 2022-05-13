# Removing-the-background-from-a-photo

В ноутбуке реализован один из нейросетевых методов удаления фона на изображении.
Нейронная сеть представляет собой модель u-net в сочетании с предобученной сетью EfficientNetV2M. u-net имеет две ветви уменьшения изображени до латентного пространства и две ветви увеличения изображения. Каждая ветвь u-net имеет разные ядра свертки. Ветвь сети EfficientNetV2M была заморожена и используется для получения фичь от изображения.
На вход опступает изображение машины на фоне (лес, природа, поле). На выход сеть выдает изображение машины на черном фоне.
Входное изображение обрабатывается двумя ветвями u-net и отдельно ветьвью EfficientNetV2M.Происходит постепенно уменьшение изображения до латентного пространства, затем полученные признаки от двух сетей конкатенируются и постепенно восстанавливаются в исходный размер изображения. В данном случае сеть была обучана на изображениях размеров 256, 384, 3.
