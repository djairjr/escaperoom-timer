// Add this to MQTTClient.cpp on_message handler:
// Add volume handling in on_message():
// if (topic == topic_prefix + "/volume_set") {
//     try {
//         int vol = std::stoi(payload);
//         vol = std::max(0, std::min(128, vol));
//         Mix_Volume(-1, vol);
//         mqtt.publish(topic_prefix + "/volume", std::to_string(vol), 1, true);
//         std::cout << "Volume set to " << vol << std::endl;
//     } catch(...) {}
// }
echo "Patch note created" 
