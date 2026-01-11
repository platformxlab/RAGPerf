#include "include/utils.hh"

namespace MSys {

template <IsProtoMessage T>
T *Meter::getCurrentBuffer() const {
    return dynamic_cast<T *>(stat_tser);
}

} // namespace MSys