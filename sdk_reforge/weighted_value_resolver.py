import random
import mmh3

max_32_float = 4_294_967_294.0


class WeightedValueResolver:
    def __init__(self, weights, key, context_hash_value):
        self.weights = weights
        self.key = key
        self.context_hash_value = context_hash_value

    def resolve(self):
        if self.context_hash_value is not None:
            percent = self.user_percent()
        else:
            percent = random.random()

        index = self.variant_index(percent)

        return (self.weights[index], index)

    def user_percent(self):
        to_hash = "%s%s" % (self.key, self.context_hash_value)
        int_value = mmh3.hash(to_hash, signed=False)
        return int_value / max_32_float

    def variant_index(self, percent):
        distribution_space = sum([w.weight for w in self.weights])
        bucket = distribution_space * percent

        bucket_sum = 0
        for index, variant_weight in enumerate(self.weights):
            if bucket < bucket_sum + variant_weight.weight:
                return index
            bucket_sum += variant_weight.weight

        return len(self.weights) - 1
